import argparse
import json
import logging
import pynetbox


def unwrap_actual_json(input_str, expected_type=None, max_iterations=10):
    '''Unpack erroneously-escaped JSON until the right type is found
    Args:
        input_str(str): String that should contain the expected JSON data structure
        expected_type(obj): Type to use for comparison, the expected result.  If None, it will iterate until a non-string result is found
        max_iterations(int): Maximum number of times to attempt unwrapping the JSON
    Returns:
        status(bool): True of data was unpacked successful
        data(obj): The JSON located, or None on failure
    '''
    iteration = 0
    data = input_str # initialize to the input string
    while iteration < max_iterations:
        try:
            data = json.loads(data)
        except json.decoder.JSONDecodeError:
            logging.error("Failed to decode: %s", input_str)
            # indicate failure
            return False, None
        if expected_type is not None and isinstance(data, expected_type) or expected_type is None and not isinstance(data, str):
            # found the expected type
            return True, data
        iteration += 1
    # if iteration count is exceeded
    return False, None

def fix_netbox_json_field(recordset, custom_field_name, max_iterations=10, make_changes=False, expected_types=(list, dict,type(None)), replace_empty_string_with_null=False):
    '''Assess the specified field, fix any non-JSON values in NetBox.  This is a work-around for https://github.com/netbox-community/netbox/issues/16640
    Args:
        custom_field_name(str): The custom_field attribute to assess
    Returns:
        nbobj_updated(list): List of NetBox objects that were fixed
        nbobj_not_updated(list): List of NetBox objects that could not be fixed
    '''
    nbobj_updated = []
    nbobj_not_updated = []
    nbobj_with_bad_value = []
    # all objects, no qualifiers currently implemented
    logging.info("Evaluating all objects")
    count_evaluated = 0
    for nbobj in recordset:
        count_evaluated += 1
        json_value = nbobj.custom_fields.get(custom_field_name)
        if json_value is None or isinstance(json_value,expected_types):
          continue
        logging.debug("Found unexpected type in NetBox object  %s %s; type is %s", nbobj, custom_field_name, type(json_value))
        logging.debug("Bad value is: %s", json_value)
        nbobj_with_bad_value.append(nbobj)
    logging.info("Evaluated %s objects, %s appear(s) to need repair", count_evaluated, len(nbobj_with_bad_value))
    for nbobj in nbobj_with_bad_value:
        # first test for an edge case of empty string, which will not decode:
        if nbobj.custom_fields.get(custom_field_name) == "" and replace_empty_string_with_null:
            status = True
            fixed_value = None
        # try getting the JSON value
        else:
            status, fixed_value = unwrap_actual_json(nbobj.custom_fields.get(custom_field_name), max_iterations=max_iterations)
        if not status:
            nbobj_not_updated.append(nbobj)
            logging.warning("Unable to unwrap json from `%s` value of NetBox object %s, value: '%s'", custom_field_name, nbobj, nbobj.custom_fields.get(custom_field_name))
            continue
        if make_changes:
            try:
                logging.debug("Updating NetBox object %s with new %s value: %s", nbobj, custom_field_name, fixed_value)
                nbobj.update({'custom_fields':{custom_field_name:fixed_value}})
                nbobj_updated.append(nbobj)
            except pynetbox.core.query.RequestError as exc:
                logging.error("Request to update %s %s value failed: %s", nbobj, custom_field_name, exc)
                nbobj_not_updated.append(nbobj)
        else:
            nbobj_updated.append(nbobj)
    return nbobj_updated, nbobj_not_updated


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog="netbox_fix_json", description="Fix JSON custom property types in NetBox, ensure they are not strings"
    )
    parser.add_argument(
        "--apitoken",
        help="NetBox API token",
        required=True
    )
    parser.add_argument(
        "--url",
        help="NetBox base URL",
        required=True
    )
    parser.add_argument(
        "--module",
        help="NetBox functional module such as 'ipam'",
        required=True
    )
    parser.add_argument(
        "--type",
        help="NetBox object type such as 'prefixes'",
        required=True
    )
    parser.add_argument(
        "--field-name",
        help="Custom field name to assess/update",
        required=True
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show details of changes, default is to print counts only"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--make-changes",
        action="store_true",
        help="Make changes, default behavior is dry run only",
    )
    parser.add_argument(
        "--max-iterations",
        help="Number of nested JSON string encodings to try and unwrap, default 10",
        type=int,
        default=10
    )
    parser.add_argument(
        "--cafile",
        help="CA cert list to use for SSL verification",
    )
    parser.add_argument(
        "--replace-empty-string-with-null",
        help="Replace empty string (bad value) with null.  This is a reasonable action but is not default behavior out of an abundance of caution.",
        action="store_true"
    )


    logging.basicConfig(level=logging.INFO)
    args = parser.parse_args()
    if args.debug:
        logging.getLogger().setLevel(level=logging.DEBUG)

    netbox = pynetbox.api(url=args.url, token=args.apitoken)
    if args.cafile:
        netbox.http_session.verify = args.cafile
    netbox_module = getattr(netbox, args.module)
    netbox_type = getattr(netbox_module, args.type)
    logging.info("Will be evaluating objects of type %s.%s", args.module, args.type)
    if args.make_changes:
        logging.info("Changes will be made and summarized at the end of the run")
    else:
        logging.info("Operating in dry-run mode (updates listed at end of run will be simulated, not actual)")
    recordset = netbox_type.all()
    objects_updated, objects_not_updated = fix_netbox_json_field(recordset, max_iterations=args.max_iterations, custom_field_name=args.field_name ,make_changes=args.make_changes, replace_empty_string_with_null=args.replace_empty_string_with_null)
    if args.verbose:
        updated_flattened = '\n  '.join([str(item) for item in objects_updated])
        not_updated_flattened = '\n  '.join([str(item) for ite in objects_not_updated])
        print(f"Objects Updated:\n  {updated_flattened}")
        print(f"Objects Not Updated:\n  {not_updated_flattened}")
    else:
        print(f"Object Count Updated: {len(objects_updated)}")
        print(f"Objects Count Not Updated: {len(objects_not_updated)}")



