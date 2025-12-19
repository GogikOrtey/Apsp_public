import requests

proxy = "http://10.0.4.112:1020"  # если прокси без авторизации
# proxy = "http://user:password@10.0.4.112:1050"  # если требуется логин/пароль

proxies = {
    "http": proxy,
    "https": proxy,
}

resp = requests.get("https://api.ipify.org", proxies=proxies, timeout=10)
resp.raise_for_status()
print("IP через прокси:", resp.text)