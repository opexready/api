from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Importa el objeto Base desde tus modelos
from app.models import Base  # Asegúrate de que la ruta es correcta según tu estructura de proyecto

# Este es el objeto de configuración de Alembic, que proporciona
# acceso a los valores dentro del archivo .ini en uso.
config = context.config

# Interpreta el archivo de configuración para el logging de Python.
# Esta línea configura básicamente los loggers.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Aquí se agrega el MetaData de tus modelos para soportar el autogenerado
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Ejecuta migraciones en modo 'offline'.

    Esto configura el contexto con solo una URL y no un Engine, aunque
    un Engine también es aceptable aquí. Al omitir la creación de un Engine,
    ni siquiera necesitamos que un DBAPI esté disponible.

    Las llamadas a context.execute() aquí emiten la cadena dada a la salida del script.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Ejecuta migraciones en modo 'online'.

    En este escenario, necesitamos crear un Engine
    y asociar una conexión con el contexto.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
