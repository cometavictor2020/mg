"""
Módulo de almacenamiento en Amazon S3.

Responsabilidad:
    Subir archivos locales al bucket S3 configurado para MotorGuardian.
"""

from pathlib import Path
import boto3
from botocore.exceptions import ClientError

def existe_objeto_s3(bucket, clave_s3):
    """
    Verifica si un objeto ya existe en Amazon S3.

    Parámetros:
        bucket: Nombre del bucket S3.
        clave_s3: Ruta/nombre del objeto dentro del bucket.

    Retorna:
        True si el objeto existe.
        False si el objeto no existe.
    """

    cliente_s3 = boto3.client("s3")

    try:
        cliente_s3.head_object(
            Bucket=bucket,
            Key=clave_s3
        )
        return True

    except ClientError as error:

        codigo_error = error.response["Error"]["Code"]

        if codigo_error == "404":
            return False

        raise

def subir_archivo_s3(ruta_local, bucket, clave_s3):
    """
    Sube un archivo local a Amazon S3.

    Parámetros:
        ruta_local: Ruta del archivo en el computador.
        bucket: Nombre del bucket S3.
        clave_s3: Ruta/nombre del objeto dentro del bucket.
    """

    ruta_local = Path(ruta_local)

    if not ruta_local.exists():
        raise FileNotFoundError(f"No existe el archivo: {ruta_local}")

    cliente_s3 = boto3.client("s3")
    if existe_objeto_s3(bucket, clave_s3):
        print(f"El objeto ya existe en S3. No se sobrescribirá: {clave_s3}")
        return False

    cliente_s3.upload_file(
        str(ruta_local),
        bucket,
        clave_s3
    )

    return True