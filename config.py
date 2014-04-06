### DEBUG
#### Adds debug functionality to the API (trace level error reporting, auto reload on file change, etc)
#### Do not run this outside of development
DEBUG = True

### ES_INDEX
#### Index to use for elasticsearch
ES_INDEX = 'opendataapiv1_2'

### MAX_QUERY_SIZE
#### Controls the maximum length of the response in items. Required for ElasticSearch
MAX_QUERY_SIZE = 50000

### TRUSTED_ADDRESSES
#### Access list of trusted IPs that have permission to delete, insert and update
TRUSTED_ADDRESSES = ['127.0.0.1']