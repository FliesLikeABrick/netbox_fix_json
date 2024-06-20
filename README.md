NetBox issue https://github.com/netbox-community/netbox/issues/16640 can corrupt data, this script helps repair data in the specified module, type, and custom field.

Example usage, in our case to evaluate a field called 'references' on all NetBox IPAM Prefixes: 
python3 netbox_fix_json.py --apitoken=[redacted] --url=https://[your netbox instance]  --fieldname=references --module=ipam --type=prefixes --field-name=references

The script is read-only by default.  Add --verbose to see the specific objects that are being updated or proposed to be updated.  Add --make-changes to affect the data changes after reviewing the output.

It may be a good idea to take a database backup before having this script make changes.
