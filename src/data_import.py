import boto3
import csv
import traceback
import sys
import codecs
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger
# from strings_util import remove_non_alphanumeric, convert_to_snake_case
import humps

LOGGER = Logger()

DYNAMO = boto3.resource("dynamodb")
DYNAMO_TABLE = DYNAMO.Table(name="my-dynamodb-table")
S3 = boto3.client('s3')
default_file = "autos.csv"

FILE_HEADERS = {
    "Ciudad": "ciudad",
    "Zona": "zona",
    "Consecionaria": "consecionaria",
    "Horario De Atencion": "horarios",
    "Direccion": "direccion",
    "Telefonos": "telefonos",
    "Contacto": "contacto",
    "Marcas De Autos": "marcas",
}


def get_delimiter(data: str):
    """Get csv delimiter and return a string
    Keyword arguments:
    data -- a row from csv
    """
    sniffer = csv.Sniffer()
    dialect = sniffer.sniff(data)
    return dialect.delimiter


def get_formatted_header(formatted_key: dict, headers: str, delimiter: str):
    """Format csv header and return a string
    """
    header_list = []
    for header in headers.split(delimiter):
        if header:
            # Mapping CSV columns with DB object keys
            formatted_header = formatted_key.get(header.lower().replace(" ", ""))
            if formatted_header:
                header_list.append(formatted_header)
            else:
                header_list.append(humps.decamelize(header))
        else:
            header_list.append("")
    return delimiter.join(header_list)


def get_list_of_objects(data: list, header_formatted_key: dict):
    """Return list of objects with formatted keys
    Keyword arguments:
    data -- list of strings
    header_formatted_key -- csv header formatted key
    """
    delimiter = get_delimiter(data[0])
    data[0] = get_formatted_header(header_formatted_key, data[0], delimiter)
    return csv.DictReader((data), delimiter=delimiter)


def handler(event, _):
    # Connect to S3
    record = event["Records"][0]
    LOGGER.info({"Record:": record})
    # get bucket name and object key (file name)
    bucket_name = record["s3"]["bucket"]["name"]
    file_name = record["s3"]["object"]["key"]

    LOGGER.info({"Bucket": f"Bucket: {bucket_name} - File: {file_name}"})

    try:
        csv_obj = S3.get_object(Bucket=bucket_name, Key=file_name)
        data = csv_obj['Body'].read().decode('utf-8-sig').splitlines()
        items = []
        LOGGER.info({"items_len": data})
        reader = get_list_of_objects(data, FILE_HEADERS)
        for row in reader:
            # LOGGER.info({"ROW": row})
            new_row = {}
            new_row['pk'] = f'ciudad:{row["ciudad"]}'
            new_row['sk'] = f'cliente:{row["consecionaria"].strip()}#{row["zona"]}'
            new_row['cliente'] = row.get("consecionaria", "desconocido")
            new_row['ciudad'] = row["ciudad"]
            new_row['zona'] = row["zona"]
            new_row['contacto'] = row["contacto"]
            new_row['marcas'] = row["marcas_de_autos"]
            new_row['horarios'] = row["horario_de_atencion"]
            new_row["telefonos"] = row["telefonos"]
            new_row['direccion'] = row["direccion"]
            LOGGER.info({"NEW_ROW": new_row})
            if (new_row.get('cliente', None)):
                items.append(new_row)

        if items:
            # populate new data
            LOGGER.info({"Message": f'Success uploaded items {len(items)}'})
            populate_table(items)
    except KeyError as kerr:
        LOGGER.error({"Error": kerr})
    except Exception as error:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        LOGGER.debug(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))


def populate_table(items):

    try:
        print(
            {
                "event": "dynamodb.batch_write.start",
                "table": "my-dynamo-table",
                "items": len(items),
            }
        )

        with DYNAMO_TABLE.batch_writer() as writer:
            for item in items:
                writer.put_item(Item=item)

        print({"event": "dynamodb.batch_write.end"})
    except ClientError as err:
        print({"event": "dynamodb.create_table.failed", "error": str(err)})
        raise err
