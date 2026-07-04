"""Auth providers: option mapping per mechanism."""

from __future__ import annotations

import pytest

from dbx_rt_ingestion.auth.providers import build_auth_provider
from dbx_rt_ingestion.config.models import AuthSpec
from dbx_rt_ingestion.core.exceptions import AuthenticationError


def test_msk_iam_options() -> None:
    provider = build_auth_provider(AuthSpec(type="msk_iam"))
    options = provider.kafka_options()
    assert options["kafka.security.protocol"] == "SASL_SSL"
    assert options["kafka.sasl.mechanism"] == "AWS_MSK_IAM"
    assert "IAMLoginModule" in options["kafka.sasl.jaas.config"]


def test_mtls_requires_keystore() -> None:
    with pytest.raises(AuthenticationError) as exc:
        build_auth_provider(
            AuthSpec(type="mtls", options={"truststore_location": "/certs/ts.jks"})
        )
    assert "keystore_location" in str(exc.value)


def test_mtls_full_options() -> None:
    provider = build_auth_provider(
        AuthSpec(
            type="mtls",
            options={
                "truststore_location": "/certs/ts.jks",
                "keystore_location": "/certs/ks.jks",
                "keystore_password": "pw",
            },
        )
    )
    options = provider.kafka_options()
    assert options["kafka.security.protocol"] == "SSL"
    assert options["kafka.ssl.keystore.location"] == "/certs/ks.jks"


def test_sasl_scram_jaas() -> None:
    provider = build_auth_provider(
        AuthSpec(type="sasl_ssl", options={"username": "svc", "password": "pw"})
    )
    options = provider.kafka_options()
    assert options["kafka.sasl.mechanism"] == "SCRAM-SHA-512"
    assert 'username="svc"' in options["kafka.sasl.jaas.config"]


def test_sasl_unsupported_mechanism() -> None:
    provider = build_auth_provider(
        AuthSpec(
            type="sasl_ssl",
            options={"username": "u", "password": "p", "mechanism": "OAUTHBEARER"},
        )
    )
    with pytest.raises(AuthenticationError):
        provider.kafka_options()


def test_kerberos_options() -> None:
    provider = build_auth_provider(
        AuthSpec(
            type="kerberos",
            options={
                "principal": "svc@CORP",
                "keytab_location": "/keytabs/svc.keytab",
            },
        )
    )
    options = provider.kafka_options()
    assert options["kafka.sasl.mechanism"] == "GSSAPI"
    assert 'principal="svc@CORP"' in options["kafka.sasl.jaas.config"]
    assert options["kafka.sasl.kerberos.service.name"] == "kafka"
