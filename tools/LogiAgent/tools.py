import json
import os
import re
from distutils.util import strtobool

import requests
from pydantic import BaseModel, Field
from typing import Annotated, Optional, Union

import global_vars_funcs_configs
import test_scenario

all_request_sequence = []
right_results = []
wrong_results = []


class DoRequestsRequestParams(BaseModel):
    base_url: Annotated[str, Field(description="REST API System Base URL")]
    method: Annotated[str, Field(description="HTTP Method")]
    api: Annotated[str, Field(description="REST API URL")]
    headers: Annotated[Optional[dict], Field(description="API Request Headers")] = Field(default_factory=dict)
    params: Annotated[Optional[dict], Field(description="API Request URL Params")] = Field(default_factory=dict)
    payload: Annotated[Optional[Union[dict, list]], Field(description="API Request Payload Body")] = Field(default_factory=dict)
    payload_type: Annotated[
        str,
        Field(description="Payload Content-Type", default="application/json")
    ]


def remove_duplicate_path_segment(base: str, api_path: str) -> str:
    """
    Remove duplicate segments between base_url.rstrip's end and api.lstrip's beginning if they match specified patterns.
    Use single forward slash when joining paths.
    """
    base_cleaned = base.rstrip('/')
    api_cleaned = api_path.lstrip('/')

    overlap_types = ["api", r"api/v\d+", r"v\d+"]

    for pattern in overlap_types:
        match_base = re.search(pattern + "$", base_cleaned)
        match_api = re.search("^" + pattern, api_cleaned)

        if match_base and match_api:
            base_segment = match_base.group(0)
            api_segment = match_api.group(0)

            if base_segment == api_segment:
                api_cleaned = api_cleaned[len(api_segment):].lstrip('/')
                break

    if base_cleaned and api_cleaned:
        return base_cleaned + "/" + api_cleaned  # Use single forward slash
    elif base_cleaned:
        return base_cleaned + "/"
    elif api_cleaned:
        return "/" + api_cleaned
    else:
        return "/" # or "", depending on requirements


def do_request(request_params: DoRequestsRequestParams) -> dict:
    """
    :param request_params: API Request parameters encapsulated in DoRequestsRequestParams object
    :return: API Response
    """
    global all_request_sequence

    base_url = request_params.base_url
    method = request_params.method
    api = request_params.api
    headers = request_params.headers or dict()
    params = request_params.params
    payload = request_params.payload
    payload_type = request_params.payload_type
    timeout = 10
    proxies = {"http": None, "https": None}

    url = remove_duplicate_path_segment(base_url, api)

    # Set Content-Type header
    if "Content-Type" not in headers:
        headers['Content-Type'] = payload_type

    try:
        method = method.upper()
        if method not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
            raise ValueError(f"Unsupported HTTP method: {method}")

        if payload is not None:
            if payload_type == "application/json":
                # JSON format
                response = requests.request(
                    method, url, headers=headers, params=params, json=payload,
                    timeout=timeout, verify=False, proxies=proxies
                )
            elif payload_type == "application/x-www-form-urlencoded":
                # URL encoded format
                response = requests.request(
                    method, url, headers=headers, params=params, data=payload,
                    timeout=timeout, verify=False, proxies=proxies
                )
            elif payload_type == "multipart/form-data":
                # File upload or form data
                response = requests.request(
                    method, url, headers=headers, params=params, files=payload,
                    timeout=timeout, verify=False, proxies=proxies
                )
            else:
                # For user-defined Content-Type, try using `data` as default handling method
                response = requests.request(
                    method, url, headers=headers, params=params, data=payload,
                    timeout=timeout, verify=False, proxies=proxies
                )
        else:
            # Case without payload
            response = requests.request(
                method, url, headers=headers, params=params,
                timeout=timeout, verify=False, proxies=proxies
            )

        try:
            response_data = response.json()
        except ValueError:
            response_data = response.text
        if isinstance(response_data, dict) or isinstance(response_data, list):
            response_data = json.dumps(response_data, separators=(',', ':'))
        if len(str(response_data)) > 3500:
            response_data = str(response_data)[:3500] + '... [JSON TOO LONG, TRUNCATED]'

        print(f"DO REQUEST: {method=} {url=} {headers=} {params=} {payload=} {payload_type=} {response_data=}")
        item = {
            "method": method,
            "api": api,
            "url": url,
            "headers": headers,
            "params": params,
            "payload": payload,
            "payload_type": payload_type,
            "request_data": f"{method=} {api=} {params=} {payload=}",
            "response_code": response.status_code,
            "response_data": response_data
        }
        # for recording json
        all_request_sequence.append(item)
        # for agent flow control
        test_scenario.add_next_response_for_validation(item)

        return {
            'status_code': response.status_code,
            'response_data': response_data,
        }
    except Exception as e:
        raise RuntimeError(f"Request failed: {e}")


def record_result(oracle: str, judge_reason: str, align_with_expected: bool, request_info: str, response: str) -> str:
    """
    :param align_with_expected: if the oracle is aligned with response
    :param request_info: request info
    :param judge_reason: the reason of the judgement
    :param oracle: oracle string, expected output
    :param response: actual response code and body
    """
    global all_request_sequence, right_results, wrong_results  # Declare global variables

    if align_with_expected:
        right_results.append({
            "request_info": request_info,
            "oracle": oracle,
            "judge_reason": judge_reason,
            "response": response
        })
    else:
        wrong_results.append({
            "request_info": request_info,
            "oracle": oracle,
            "judge_reason": judge_reason,
            "response": response
        })

    print(f"[Invoke record_result] {align_with_expected=} {len(right_results)=} {len(wrong_results)=}")

    return f"finished record_result: {align_with_expected=}"
