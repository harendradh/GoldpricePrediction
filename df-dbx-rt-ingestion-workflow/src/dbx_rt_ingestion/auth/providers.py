"""Authentication providers mapped to Kafka client security options.

Each provider converts an :class:`AuthSpec` into fully-qualified Spark Kafka
reader options (``kafka.*``). Secret placeholders in the spec are already
resolved by the loader before providers see them.

Supported: none, ssl, mtls, sasl_ssl (SCRAM/PLAIN), msk_iam, kerberos (GSSAPI).
New mechanisms register in ``auth_registry`` without framework changes.
"""

from __future__ import annotations

from dbx_rt_ingestion.config.models import AuthSpec
from dbx_rt_ingestion.core.exceptions import AuthenticationError
from dbx_rt_ingestion.core.interfaces import AuthProvider
from dbx_rt_ingestion.core.registry import Registry

auth_registry: Registry[AuthProvider] = Registry("auth provider")


def build_auth_provider(spec: AuthSpec) -> AuthProvider:
    """Instantiate the provider named by ``spec.type``."""

    return auth_registry.create(spec.type, spec=spec)


class BaseAuthProvider(AuthProvider):
    """Shared option handling for all providers."""

    #: options this provider requires in ``AuthSpec.options``
    required_options: tuple[str, ...] = ()

    def __init__(self, spec: AuthSpec) -> None:
        self.spec = spec
        missing = [opt for opt in self.required_options if opt not in spec.options]
        if missing:
            raise AuthenticationError(
                f"Auth provider '{spec.type}' is missing required options",
                context={"missing": missing, "required": list(self.required_options)},
            )

    def _opt(self, key: str, default: str | None = None) -> str:
        value = self.spec.options.get(key, default)
        if value is None:
            raise AuthenticationError(
                f"Auth provider '{self.spec.type}' missing option '{key}'"
            )
        return value


@auth_registry.register("none")
class NoAuthProvider(BaseAuthProvider):
    """PLAINTEXT — non-production / local testing only."""

    def kafka_options(self) -> dict[str, str]:
        return {"kafka.security.protocol": "PLAINTEXT"}


@auth_registry.register("ssl")
class SslAuthProvider(BaseAuthProvider):
    """One-way TLS: broker certificate verification via truststore."""

    required_options = ("truststore_location",)

    def kafka_options(self) -> dict[str, str]:
        options = {
            "kafka.security.protocol": "SSL",
            "kafka.ssl.truststore.location": self._opt("truststore_location"),
            "kafka.ssl.truststore.type": self._opt("truststore_type", "JKS"),
        }
        if "truststore_password" in self.spec.options:
            options["kafka.ssl.truststore.password"] = self._opt("truststore_password")
        return options


@auth_registry.register("mtls")
class MutualTlsAuthProvider(SslAuthProvider):
    """Mutual TLS: adds client keystore to one-way TLS."""

    required_options = ("truststore_location", "keystore_location", "keystore_password")

    def kafka_options(self) -> dict[str, str]:
        options = super().kafka_options()
        options.update(
            {
                "kafka.ssl.keystore.location": self._opt("keystore_location"),
                "kafka.ssl.keystore.password": self._opt("keystore_password"),
                "kafka.ssl.keystore.type": self._opt("keystore_type", "JKS"),
            }
        )
        if "key_password" in self.spec.options:
            options["kafka.ssl.key.password"] = self._opt("key_password")
        return options


@auth_registry.register("sasl_ssl")
class SaslSslAuthProvider(BaseAuthProvider):
    """SASL over TLS. Mechanisms: SCRAM-SHA-512 (default), SCRAM-SHA-256, PLAIN."""

    required_options = ("username", "password")

    _JAAS_MODULES = {
        "SCRAM-SHA-512": "org.apache.kafka.common.security.scram.ScramLoginModule",
        "SCRAM-SHA-256": "org.apache.kafka.common.security.scram.ScramLoginModule",
        "PLAIN": "org.apache.kafka.common.security.plain.PlainLoginModule",
    }

    def kafka_options(self) -> dict[str, str]:
        mechanism = self._opt("mechanism", "SCRAM-SHA-512").upper()
        module = self._JAAS_MODULES.get(mechanism)
        if module is None:
            raise AuthenticationError(
                f"Unsupported SASL mechanism '{mechanism}'",
                context={"supported": sorted(self._JAAS_MODULES)},
            )
        jaas = (
            f'{module} required username="{self._opt("username")}" '
            f'password="{self._opt("password")}";'
        )
        options = {
            "kafka.security.protocol": "SASL_SSL",
            "kafka.sasl.mechanism": mechanism,
            "kafka.sasl.jaas.config": jaas,
        }
        if "truststore_location" in self.spec.options:
            options["kafka.ssl.truststore.location"] = self._opt("truststore_location")
        return options


@auth_registry.register("msk_iam")
class MskIamAuthProvider(BaseAuthProvider):
    """AWS MSK IAM authentication (aws-msk-iam-auth library on the cluster)."""

    def kafka_options(self) -> dict[str, str]:
        return {
            "kafka.security.protocol": "SASL_SSL",
            "kafka.sasl.mechanism": "AWS_MSK_IAM",
            "kafka.sasl.jaas.config": (
                "software.amazon.msk.auth.iam.IAMLoginModule required;"
            ),
            "kafka.sasl.client.callback.handler.class": (
                "software.amazon.msk.auth.iam.IAMClientCallbackHandler"
            ),
        }


@auth_registry.register("kerberos")
class KerberosAuthProvider(BaseAuthProvider):
    """Kerberos / GSSAPI — typical for Cloudera Kafka."""

    required_options = ("principal", "keytab_location")

    def kafka_options(self) -> dict[str, str]:
        jaas = (
            "com.sun.security.auth.module.Krb5LoginModule required "
            "useKeyTab=true storeKey=true "
            f'keyTab="{self._opt("keytab_location")}" '
            f'principal="{self._opt("principal")}";'
        )
        options = {
            "kafka.security.protocol": self._opt("security_protocol", "SASL_SSL"),
            "kafka.sasl.mechanism": "GSSAPI",
            "kafka.sasl.kerberos.service.name": self._opt("service_name", "kafka"),
            "kafka.sasl.jaas.config": jaas,
        }
        if "truststore_location" in self.spec.options:
            options["kafka.ssl.truststore.location"] = self._opt("truststore_location")
        return options
