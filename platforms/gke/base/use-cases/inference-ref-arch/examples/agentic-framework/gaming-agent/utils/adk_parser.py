import json
import logging
from typing import List, Dict, Any

# Get the logger instance from the centralized logging setup
from .logging_setup import app_logger as logger # Import the configured logger

def parse_adk_output_event(event_dict: Dict[str, Any]) -> tuple[str, List[Dict[str, Any]]]:
    """
    Processes a single output_event_dict from AdkApp.async_stream_query
    to extract text responses and structured tool outputs,
    enriching them with event metadata for traceability.
    Returns a tuple of (extracted_text: str, extracted_tool_outputs: List[Dict[str, Any]]).
    """
    extracted_text = ""
    extracted_tool_outputs = []

    event_type = event_dict.get('type')
    event_author = event_dict.get('author')
    event_invocation_id = event_dict.get('invocation_id')
    event_id = event_dict.get('id')
    event_timestamp = event_dict.get('timestamp')

    logger.debug(f"Parsing event: Type={event_type}, Author={event_author}, InvocationID={event_invocation_id}")

    if event_dict.get('text_response'):
        current_text = str(event_dict['text_response'])
        extracted_text += current_text
        logger.debug(f"Event text_response: {current_text[:100]}...")
    elif event_dict.get('text'):
        current_text = str(event_dict['text'])
        extracted_text += current_text
        logger.debug(f"Event text: {current_text[:100]}...")

    if event_dict.get('tool_response') is not None:
        tool_response_data = event_dict['tool_response']
        logger.debug(f"Raw tool_response_data type: {type(tool_response_data)}")
        logger.debug(f"Raw tool_response_data value: {tool_response_data}")

        tool_output_meta = {
            "event_type": event_type,
            "event_author": event_author,
            "event_invocation_id": event_invocation_id,
            "event_id": event_id,
            "event_timestamp": event_timestamp,
            "tool_response_raw": tool_response_data
        }

        if isinstance(tool_response_data, str):
            try:
                parsed_tool_data = json.loads(tool_response_data)
                tool_output_meta['tool_output_parsed'] = parsed_tool_data
                extracted_tool_outputs.append(tool_output_meta)
                logger.debug(f"Event tool_response (parsed JSON): {parsed_tool_data}")
            except json.JSONDecodeError:
                tool_output_meta['raw_tool_response'] = tool_response_data
                extracted_tool_outputs.append(tool_output_meta)
                logger.debug(f"Event tool_response (raw string): {tool_response_data[:100]}...")
        elif isinstance(tool_response_data, dict):
            tool_output_meta['tool_output_dict'] = tool_response_data
            extracted_tool_outputs.append(tool_output_meta)
            logger.debug(f"Event tool_response (dict): {tool_response_data}")
        elif isinstance(tool_response_data, list):
            tool_output_meta['tool_result_list'] = tool_response_data
            extracted_tool_outputs.append(tool_output_meta)
            logger.debug(f"Event tool_response (list): {tool_response_data}")
        else:
            tool_output_meta['raw_tool_response_untyped'] = str(tool_response_data)
            extracted_tool_outputs.append(tool_output_meta)
            logger.debug(f"Event tool_response (other type): {str(tool_response_data)[:100]}...")

    content_dict = event_dict.get('content')
    if isinstance(content_dict, dict) and 'parts' in content_dict and isinstance(content_dict['parts'], list):
        for part_dict in content_dict['parts']:
            if isinstance(part_dict, dict):
                if 'function_response' in part_dict and part_dict['function_response']:
                    logger.debug(f"Found 'function_response' in content part dictionary: {part_dict['function_response']}")
                    extracted_tool_outputs.append({
                        "event_type": event_type,
                        "event_author": event_author,
                        "event_invocation_id": event_invocation_id,
                        "event_id": event_id,
                        "event_timestamp": event_timestamp,
                        'tool_name': part_dict['function_response'].get('name'),
                        'tool_output': part_dict['function_response'].get('response')
                    })
                elif 'function_call' in part_dict and part_dict['function_call']:
                    logger.debug(f"Found 'function_call' in content part dictionary: {part_dict['function_call']}")
                    extracted_tool_outputs.append({
                        "event_type": event_type,
                        "event_author": event_author,
                        "event_invocation_id": event_invocation_id,
                        "event_id": event_id,
                        "event_timestamp": event_timestamp,
                        'tool_name': part_dict['function_call'].get('name'),
                        'tool_args': part_dict['function_call'].get('args'),
                        'action_type': 'function_call'
                    })
                elif 'text' in part_dict and part_dict['text']:
                    current_text = str(part_dict['text'])
                    extracted_text += current_text
                    logger.debug(f"Found 'text' in content part dictionary: {current_text[:100]}...")
                else:
                    logger.debug(f"Content part dictionary is not recognized (func_resp, func_call, text): {part_dict.keys()}")
    elif isinstance(content_dict, dict):
        if content_dict.get('function_response'):
            logger.debug(f"Found 'function_response' directly in content dictionary: {content_dict['function_response']}")
            extracted_tool_outputs.append({
                "event_type": event_type,
                "event_author": event_author,
                "event_invocation_id": event_invocation_id,
                "event_id": event_id,
                "event_timestamp": event_timestamp,
                'tool_name': content_dict['function_response'].get('name'),
                'tool_output': content_dict['function_response'].get('response')
            })
        elif content_dict.get('function_call'):
            logger.debug(f"Found 'function_call' directly in content dictionary: {content_dict['function_call']}")
            extracted_tool_outputs.append({
                "event_type": event_type,
                "event_author": event_author,
                "event_invocation_id": event_invocation_id,
                "event_id": event_id,
                "event_timestamp": event_timestamp,
                'tool_name': content_dict['function_call'].get('name'),
                'tool_args': content_dict['function_call'].get('args'),
                'action_type': 'function_call'
            })
        elif content_dict.get('text'):
            current_text = str(content_dict['text'])
            extracted_text += current_text
            logger.debug(f"Found 'text' directly in content dictionary: {current_text[:100]}...")
        else:
            logger.debug(f"Content is a dict but not recognized (func_resp, func_call, text): {content_dict.keys()}")
    else:
        if content_dict is not None:
            logger.debug(f"Content is not a recognized type for parsing: {type(content_dict)}")

    if not extracted_text and (event_type or event_author):
        logger.debug(f"Processed event with type '{event_type}' from '{event_author}'. No text extracted.")

    return extracted_text, extracted_tool_outputs

