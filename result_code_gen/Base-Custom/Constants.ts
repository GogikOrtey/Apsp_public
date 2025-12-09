import { AsyncHTTPXRequestOptsCustom, CommandCurlCffi, CommandFlareSolver, CommandTlsClient, defaultConf, editableConf, field } from "./Types";
import { BaseParser, SetType } from "a-parser-types";
import { Cacher } from "../Base-Custom/Cache";
import { resultFormatter } from "./Fields";

export const second = 1
export const minute = second * 60
export const hour = minute * 60
export const day = hour * 24

/**
 * Функция для получения дефолтного конфига парсера
 * @param fields Собираемые поля парсером
 * @param resultFormatSeparator Сепаратор для разделителя в строке результатов
 * @returns Конфиг
*/
export function getDefaultConf(fields: field[], resultFormatSeparator: string = "§", flatFields: field[] = []): defaultConf {
    return {
        results: {
            arrays: {
                items: ["Items list", fields],
            },
            flat: flatFields,
        },
        results_format: resultFormatter(fields, resultFormatSeparator),
        max_size: 1024 * 1024 * 2,
        proxyretries: 10,
        requestdelay: "1,3",

        pagesCount: 1,
        itemsCount: 3,
        cache_hours: 18,
        force_parse: false,
        debug: false,
        engine: "a-parser",
        mode: "normal",
    }
}

export const defaultEditableConf: editableConf = [
    ["pagesCount", ["textfield", "Кол-во собираемых страниц поиска"]],
    ["itemsCount", ["textfield", "Кол-во собираемых товаров с 1 страницы поиска"]],
    ["cache_hours", ["textfield", "Кол-во часов кеширования"]],
    ["force_parse", ["checkbox", "Не проверять в кеше"]],
    ["debug", ["checkbox", "Дебаг логи"]],
    [
        "engine",
        [
            "combobox",
            "Движок запроса",
            { multiSelect: 0 },
            ["a-parser", "a-parser"],
            ["curlCffi", "curlCffi"],
            ["tlsClient", "tlsClient"]
        ]
    ],
    [
        "mode",
        [
            "combobox",
            "Режим обработки запроса",
            { multiSelect: 0 },
            ["normal", "normal"],
            ["flaresolver", "flaresolver"]
        ]
    ],
]

/**
 * Функция для получения кешера
 * @param parser Объект парсера, нужно передать просто this
 * @param set<SetType> Объект set
 * @param cacheParams - Парметры кеширования. Дефолтное значение { link: set.query, region: set.region }
 * @returns Объект кешера
 */
export function getCacher<T>(parser: BaseParser, set: SetType, cacheParams?: {}) {
    return new Cacher<T[]>(
        parser, parser.conf.cache_hours || 18,
        cacheParams || { link: set.query, region: set.region },
        parser.conf.force_parse || false, "items"
    )
}

export const defaultOpts: AsyncHTTPXRequestOptsCustom = {
    decode: "auto-html",
    browser: 1,
    tlsOpts: { rejectUnauthorized: false },
};

// Для нормальной обработки мониторингов леманы
export const LEMENA_MONITORINGS = [
    "3ad66c1d-d889-4822-8b29-4c3d9f445fc4", // LEMANA PRO
    "21a9f6ba-8400-4eb2-b7fe-39e586446add", // LEMANA PRO доработки
    "17adf0ea-5559-44f5-b504-c442078f6dab", // LEMANA PRO KZ
    // "895fcbc1-7d5a-4091-b0fd-8a41d62cbf65", // LEMANA PRO матчинги ВОДОСНАБЖЕНИЕ_СВЕТ_ХРАНЕНИЕ
    // "93815af3-a283-4abe-9e47-9436cf8dd36b", // LEMANA PRO матчинги САНТЕХНИКА_ОТДЕЛОЧНЫЕ МАТЕРИАЛЫ_КУХНИ
    // "b443e714-955d-4bb9-b284-39ae6505f0bc", // LEMANA PRO матчинги ЭЛЕКТРОТОВАРЫ_НАПОЛЬНЫЕ ПОКРЫТИЯ_КРАСКИ
    // "002871b1-4868-4f81-a6e7-8099802ca6fb", // LEMANA PRO матчинги СТРОЙМАТЕРИАЛЫ_СТОЛЯРНЫЕ ИЗДЕЛИЯ_ИНСТРУМЕНТЫ
    // "00b3a9aa-49d6-4a25-994d-4e65173fc0e0", // LEMANA PRO матчинги ПЛИТКА_САД_СКОБЯНЫЕ ИЗДЕЛИЯ
]


export class OptsGenerators {
    static getOptsForCF(url: string, urlParams: {}, opts: AsyncHTTPXRequestOptsCustom, proxy?: {
        url: string,
        username?: string,
        password?: string
    }): AsyncHTTPXRequestOptsCustom {
        let _url = new URL(url)
        if (urlParams && Object.entries(urlParams).length > 0) {
            Object.entries(urlParams).map(([k, v]) => _url.searchParams.append(k, v as string))
        }
        if (!opts.flaresolver_params) opts.flaresolver_params = {}
        if (!opts.flaresolver_params.cmd) opts.flaresolver_params.cmd = "request.get"
        if (typeof opts.flaresolver_params.use_headers === "undefined") opts.flaresolver_params.use_headers = true
        const command: CommandFlareSolver = {
            ...opts.flaresolver_params,
            url: _url.href,
            maxTimeout: (opts.timeout || 120) * 1000,
            ...(proxy && typeof proxy !== "undefined") && { proxy }
        }
        if (opts.flaresolver_params.preferredChallengeWorker) {//@ts-ignore
            delete command.preferredChallengeWorker
            command.preferred_challenge = opts.flaresolver_params.preferredChallengeWorker.providerName
        }
        if (opts.flaresolver_params.use_headers) command.headers = opts.headers
        if (opts.flaresolver_params.cmd === "request.post" || opts.flaresolver_params.cmd === "request.enhancedpost") {
            command.postData = opts.body || ""
        }
        if (opts.cookies && !opts.flaresolver_params.cookies) command.cookies = opts.cookies
        const resOpts: AsyncHTTPXRequestOptsCustom = {
            decode: "utf8",
            browser: 1,
            use_proxy: 0,
            proxyretries: 1,
            timeout: opts.timeout || 120,
            parsecodes: {
                ...opts.parsecodes,
                500: 1,
                597: 1,
                520: 1,
                503: 1,
                406: 1,
            },
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(command),
            tlsOpts: { rejectUnauthorized: false },
            check_content: [
                ...(opts.check_content || []),
            ]
        }
        return resOpts
    }

    static getOptsForCurlCffi(
        method: 'GET' | 'HEAD' | 'POST' | 'PUT' | 'DELETE' | 'CONNECT' | 'OPTIONS' | 'TRACE' | 'PATCH',
        url: string,
        urlParams: {},
        opts: AsyncHTTPXRequestOptsCustom, proxy: string): AsyncHTTPXRequestOptsCustom {
        let _url = new URL(url)
        if (urlParams && Object.entries(urlParams).length > 0) {
            Object.entries(urlParams).map(([k, v]) => _url.searchParams.append(k, v as string))
        }
        if (!opts.curlCffi_params) opts.curlCffi_params = {}
        const command: CommandCurlCffi = {
            link: decodeURI(_url.href),
            proxy: proxy,
            akamai: opts.curlCffi_params.akamai,
            ja3: opts.curlCffi_params.ja3,
            method: method,
            headers: opts.headers,
            get_all_info: true,
        }
        if (typeof opts.curlCffi_params.impersonate === "object" && opts.curlCffi_params.impersonate.length > 0) {
            command.impersonate = opts.curlCffi_params.impersonate[Math.floor(Math.random() * opts.curlCffi_params.impersonate.length)]
        } else if (typeof opts.curlCffi_params.impersonate === "string") {
            command.impersonate = opts.curlCffi_params.impersonate
        }
        if (opts.body) {
            command.body = opts.body
            if (typeof opts.curlCffi_params.body_is_json === "boolean") {
                command.body_is_json = opts.curlCffi_params.body_is_json
            } else {
                try {
                    JSON.parse(opts.body as string)
                    command.body_is_json = true
                } catch {
                    command.body_is_json = false
                }
            }
        }
        if (opts.json) {
            command.body = opts.json
            command.body_is_json = true
        }
        if (opts.headers && Object.keys(opts.headers).length === 0) {
            command.headers = { "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36", "Accept": "application/json, text/plain, */*", "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3", "Accept-Encoding": "gzip, deflate, br, zstd", "X-Requested-With": "XMLHTTPRequest", "Connection": "keep-alive", "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-site", "Pragma": "no-cache", "Cache-Control": "no-cache" }
        } else {
            command.headers = opts.headers
        }
        const resOpts: AsyncHTTPXRequestOptsCustom = {
            decode: "utf8",
            browser: 1,
            use_proxy: 0,
            proxyretries: 1,
            timeout: opts.timeout || 120,
            parsecodes: {
                ...opts.parsecodes
            },
            headers: {
                'Content-Type': 'application/json',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
            },
            body: JSON.stringify(command),
            tlsOpts: { rejectUnauthorized: false },
        }
        return resOpts;
    }

    static getOptsForTlsClient(
        method: "GET" | "HEAD" | "POST" | "PUT" | "DELETE" | "CONNECT" | "OPTIONS" | "TRACE" | "PATCH",
        url: string,
        urlParams: {},
        opts: AsyncHTTPXRequestOptsCustom, proxy: string): AsyncHTTPXRequestOptsCustom {
        let _url = new URL(url)
        if (urlParams && Object.entries(urlParams).length > 0) {
            Object.entries(urlParams).map(([k, v]) => _url.searchParams.append(k, v as string))
        }
        if (!opts.tlsClient_params) opts.tlsClient_params = {}
        const command: CommandTlsClient = {
            url: decodeURI(_url.href),
            proxy: proxy,
            method: method,
            headers: opts.headers,
            json: opts.json,
            cookies: opts.cookies,
            ja3: opts.tlsClient_params.ja3,
            is_data_bytes: opts.tlsClient_params.is_data_bytes || false,
            is_data_hex: opts.tlsClient_params.is_data_hex || false,
            allow_redirects: typeof opts.tlsClient_params.allow_redirects === "undefined" ? true : opts.tlsClient_params.allow_redirects,
        }
        if (opts.tlsClient_params.is_data_bytes) command.bytes = opts.body?.toString()
        else if (opts.tlsClient_params.is_data_hex) command.hex = opts.body?.toString()
        else command.data = opts.body?.toString()
        if (typeof opts.tlsClient_params.preset === "object" && opts.tlsClient_params.preset.length > 0) {
            command.preset = opts.tlsClient_params.preset[Math.floor(Math.random() * opts.tlsClient_params.preset.length)]
        } else if (typeof opts.tlsClient_params.preset === "string") {
            command.preset = opts.tlsClient_params.preset
        }
        if (opts.headers && Object.keys(opts.headers).length === 0) {
            command.headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "X-Requested-With": "XMLHTTPRequest",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                "Pragma": "no-cache",
                "Cache-Control": "no-cache"
            }
        } else {
            command.headers = opts.headers
        }
        const resOpts: AsyncHTTPXRequestOptsCustom = {
            decode: "utf8",
            browser: 1,
            use_proxy: 0,
            proxyretries: 1,
            timeout: opts.timeout || 120,
            parsecodes: {
                ...opts.parsecodes
            },
            headers: {
                'Content-Type': 'application/json',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
            },
            body: JSON.stringify(command),
            tlsOpts: { rejectUnauthorized: false },
        }
        return resOpts;
    }
}