🟠 Ошибка генерации: 🟠

Traceback (most recent call last):
  File "C:\Users\gogor\OneDrive\Рабочий стол\APSP_public\MAIN.py", line 114, in main_funk_start_on_front
    result_code = main_processer(link)
  File "C:\Users\gogor\OneDrive\Рабочий стол\APSP_public\new_program\main_processer.py", line 171, in main_processer
    html_content = get_shared_page().content()
  File "c:\Users\gogor\AppData\Local\Programs\Python\Python310\lib\site-packages\playwright\sync_api\_generated.py", line 8946, in content
    return mapping.from_maybe_impl(self._sync(self._impl_obj.content()))
  File "c:\Users\gogor\AppData\Local\Programs\Python\Python310\lib\site-packages\playwright\_impl\_sync_base.py", line 115, in _sync
    return task.result()
  File "c:\Users\gogor\AppData\Local\Programs\Python\Python310\lib\site-packages\playwright\_impl\_page.py", line 535, in content
    return await self._main_frame.content()
  File "c:\Users\gogor\AppData\Local\Programs\Python\Python310\lib\site-packages\playwright\_impl\_frame.py", line 475, in content
    return await self._channel.send("content", None)
  File "c:\Users\gogor\AppData\Local\Programs\Python\Python310\lib\site-packages\playwright\_impl\_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
  File "c:\Users\gogor\AppData\Local\Programs\Python\Python310\lib\site-packages\playwright\_impl\_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
playwright._impl._errors.TargetClosedError: Page.content: Target page, context or browser has been closed
