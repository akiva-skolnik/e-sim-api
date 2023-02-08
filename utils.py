"""utils.py"""
import json
import os
from re import finditer

import requests
from flask import jsonify
from lxml.html import fromstring


def chunker(seq, size):
    """chunker"""
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))


def camelCase(st):
    """camelCase"""
    output = ''.join(x for x in st.title() if x.isalnum())
    return output[0].lower() + output[1:]


def camel_case_merge(identifier):
    """camel case merge"""
    matches = finditer('.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)', identifier)
    return " ".join([m.group(0) for m in matches]).title()


def get_id(string):
    """get id"""
    return "".join(x for x in string.split("=")[-1].split("&")[0] if x.isdigit())


def get_ids_from_path(tree, path):
    """get ids from path"""
    ids = tree.xpath(path + ("/@href" if "/@href" not in path else ""))
    if ids and any("#" == x for x in ids):
        ids = [get_id([y for y in x.values() if "Utils" in y or ".html" in y][0]) for x in tree.xpath(path)]
    else:
        ids = [x.split("=")[-1].split("&")[0].strip() for x in ids]
    return ids


def get_tree(url):
    """get tree"""
    return fromstring(requests.get(url, timeout=50, verify=False).text)


def prepare_request(output):
    """prepare request"""
    response = jsonify(output)
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


def find_one(collection: str, _id: str) -> dict:
    """find one"""
    filename = f"../db/{collection}_{_id}.json"
    if os.path.exists(filename):
        with open(filename, "r", encoding='utf-8') as file:
            return json.load(file)
    else:
        return {}


def replace_one(collection: str, _id: str, data: dict) -> None:
    """replace one"""
    filename = f"../db/{collection}_{_id}.json"
    with open(filename, "w", encoding='utf-8', errors='ignore') as file:
        json.dump(data, file)
