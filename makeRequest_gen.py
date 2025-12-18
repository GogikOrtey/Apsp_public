### В этом скрипте собираются makeRequest

# Подключение всех библиотек
from import_all_libraries import * 

# Вынесенные отдельно функции
from extracting_selector_from_html import * 


# На первое время - просто возвращаем стандартный шаблон
def simple_makeRequest():
    template_simple_makeRequest = Template("""
    async makeRequest(url: string) {
        const opts: AsyncHTTPXRequestOptsCustom = {
            ...defaultOpts,
            engine: this.conf.engine,
            mode: this.conf.mode,
        };
        this.debugger.put(opts)

        const { success, headers, data } = await this.request("GET", url, {}, opts);
        this.debugger.put(data)

        if (!success || typeof data !== "string") throw new Error("Неудачный запрос");
        if (headers.Status === 404) throw new NotFoundError();

        return data;
    }
    """)

    return template_simple_makeRequest.substitute().strip()
