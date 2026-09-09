from django.core import signing


OAUTH_STATE_SALT = "stockflow.integrations.oauth-state.v2"
OAUTH_STATE_MAX_AGE_SECONDS = 10 * 60


def create_oauth_state(
    *,
    category,
    provider,
    business_id,
    connection_id,
    user_id,
):
    return signing.dumps(
        {
            "category": str(category),
            "provider": str(provider),
            "businessId": str(business_id),
            "connectionId": str(connection_id),
            "userId": str(user_id),
        },
        salt=OAUTH_STATE_SALT,
        compress=True,
    )


def read_oauth_state(raw_state, *, category, provider):
    try:
        payload = signing.loads(
            raw_state,
            salt=OAUTH_STATE_SALT,
            max_age=OAUTH_STATE_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired as exc:
        raise ValueError("The provider authorization request expired.") from exc
    except signing.BadSignature as exc:
        raise ValueError("The provider authorization state is invalid.") from exc

    if (
        payload.get("category") != str(category)
        or payload.get("provider") != str(provider)
    ):
        raise ValueError("The provider authorization state does not match.")
    return payload
