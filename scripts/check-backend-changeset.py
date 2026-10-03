#!/usr/bin/env python3
"""Fail closed on database removal, addition or possible replacement."""

import json
import sys


def validate(data):
    if (
        data.get("Status") != "CREATE_COMPLETE"
        or data.get("ExecutionStatus") != "AVAILABLE"
    ):
        raise ValueError("Change set is not executable")
    if data.get("NextToken"):
        raise ValueError("Incomplete change set; refusing execution")
    for change in data["Changes"]:
        resource = change["ResourceChange"]
        if resource["ResourceType"].startswith("AWS::RDS::"):
            if resource["Action"] != "Modify" or resource.get("Replacement") != "False":
                raise ValueError("Database removal/replacement/addition is forbidden")
    return data["ChangeSetId"]


if __name__ == "__main__":
    try:
        print(validate(json.load(sys.stdin)))
    except Exception:
        sys.exit(
            "Unsafe or incomplete backend change set; public stack execution refused"
        )
