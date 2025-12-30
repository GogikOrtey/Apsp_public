🟠 Ошибка генерации: 🟠

Traceback (most recent call last):
  File "C:\Users\gogor\OneDrive\Рабочий стол\APSP_public\MAIN.py", line 114, in main_funk_start_on_front
    result_code = main_processer(link)
  File "C:\Users\gogor\OneDrive\Рабочий стол\APSP_public\new_program\main_processer.py", line 181, in main_processer
    HGF_result = HGF_main_page_selector_and_semantic_handler(html_content_zip)
  File "C:\Users\gogor\OneDrive\Рабочий стол\APSP_public\new_program\HGF_main_page_selector_and_semantic_handler.py", line 188, in HGF_main_page_selector_and_semantic_handler
    result_request = send_message_to_ChatGPT(request_from_LLM, temperature = 0.1, system_prompt = SYSTEM_PROMPT)
  File "C:\Users\gogor\OneDrive\Рабочий стол\APSP_public\ChatGPT\OpenAI_ChatGPT.py", line 512, in send_message_to_ChatGPT
    response = _openai_responses_create_with_retry(params)
  File "C:\Users\gogor\OneDrive\Рабочий стол\APSP_public\ChatGPT\OpenAI_ChatGPT.py", line 82, in _openai_responses_create_with_retry
    resp = client.responses.create(**params)
  File "c:\Users\gogor\AppData\Local\Programs\Python\Python310\lib\site-packages\openai\resources\responses\responses.py", line 735, in create
    return self._post(
  File "c:\Users\gogor\AppData\Local\Programs\Python\Python310\lib\site-packages\openai\_base_client.py", line 1249, in post
    return cast(ResponseT, self.request(cast_to, opts, stream=stream, stream_cls=stream_cls))
  File "c:\Users\gogor\AppData\Local\Programs\Python\Python310\lib\site-packages\openai\_base_client.py", line 1037, in request
    raise self._make_status_error_from_response(err.response) from None
openai.PermissionDeniedError: Error code: 403 - {'error': {'code': 'unsupported_country_region_territory', 'message': 'Country, region, or territory not supported', 'param': None, 'type': 'request_forbidden'}}
