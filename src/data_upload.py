import boto3
import csv
from csv import reader
import traceback
import sys
import codecs
from botocore.exceptions import ClientError
# from strings_util import remove_non_alphanumeric, convert_to_snake_case
import humps


DYNAMO = boto3.resource("dynamodb")
DYNAMO_TABLE = DYNAMO.Table(name="my-dynamodb-table")
default_file = "talleres.csv"

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


def process_file(file):
    '''
    Function to prcess csv file and insert data to dynamodb table
    '''
    keys = ['ciudad', 'taller', 'zona', 'direccion', 'telefonos', 'horarios', 'contacto']
    try:
        with (codecs.open(file, 'r', encoding='utf-8-sig')) as f:
            csv_reader = reader(f, delimiter=';', )
            items = []
            count = 0
            for row in csv_reader:
                if count ==0: count+=1; continue
                new_row = dict(zip(keys, row))
                new_row['pk'] = f'ciudad:{row[0]}'
                new_row['sk'] = f'taller:{row[1].strip()}#{row[2]}'

                print({"ROW": new_row})
                items.append(new_row)

            if items:
            # populate new data
                print({"Message": f'Success uploaded items {len(items)}'})
                populate_table(items)
    except KeyError as kerr:
        print({"Error": kerr})
    except Exception as error:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        print(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))


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


process_file(default_file)