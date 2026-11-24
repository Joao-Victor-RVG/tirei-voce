from app.core.config import Settings


def init_sentry(settings: Settings) -> None:
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        # Nada de dados pessoais, corpos ou variáveis locais: podem conter o resultado do sorteio.
        data_collection={
            "user_info": False,
            "http_bodies": [],
            "database_query_data": False,
            "stack_frame_variables": False,
        },
        max_request_body_size="never",
    )
