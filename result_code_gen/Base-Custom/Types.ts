import { AsyncHTTPXRequestOpts } from "a-parser-types"
import { CustomCookiesJar } from "./CustomCookies"
import { HeadersType } from "a-parser-types";
import { BanError } from "./Errors";

/** Движок, который будет использован для запроса.
 * @param a-parser - запросы будут отправляться через a-parser
 * @param curlCffi - запросы будут отправляться через curlCffi 10.0.4.69:1337
 * @param tlsClient - запросы будут отправляться через tls-client2 10.0.4.69:46064
 */
export type Engine = "curlCffi" | "tlsClient" | "a-parser"

export type Mode = "normal" | "flaresolver"

export type baseItem = {
    stock: "InStock" | "OutOfStock",
    timestamp: number,
}

export type Item<Fields> = { [K in keyof Fields]: K extends keyof baseItem ? baseItem[K] : string }

export type field = [
    variableName: string,
    title: string
]

export interface CommandFlareSolver {
    url: string,
    cmd?: "request.get" | "request.post" | "request.clickonelement" | "request.waitforurl" | "request.enhancedpost",
    waiting_url?: string,
    cookies?: Cookie[],
    maxTimeout?: number,
    proxy?: { url: string, username?: string, password?: string },
    driver?: "uc" | "gecko",
    manipulator?: "playwright" | "selenium" | "nodriver",
    headfull?: boolean,
    selector?: string,
    selectortype?: "xpath" | "css selector" | "id" | "class name",
    selector_wait_time?: number,
    postData?: string | Buffer,
    returnOnlyCookies?: boolean,
    flag?: "headfull" | "ozon" | "cloudflare" | "gatecrasher",
    headers?: { [key: string]: string },
    keys_of_local_storage?: string[],
    preferred_challenge?: string,
}

/**
 * @param server - ссылка на распределялку, указывается для тестирования (http://10.0.4.215:9000)
 * @param cmd - команда для запроса на решалку. defalut - request.get
 * @param postData Body для request.post. В решалке отправляет ajax запрос по ссылке.
 * @param driver - движок, который будет использован для запроса. defalut - gecko
 * @param manipulator - библиотека, используемая для манипуляции драйвером. default - playwright
 * @param headfull - Нужно ли использовать headfull браузер для решения. default - false
 * @param flag - переменная служит показателем блокирования решалок. Когда запросов с данным флагом нет, данные сервеа могут использоваться свободно
 * @param cookies список кук, которые будут переопределены opts.cookies
 * @param useSolvedProxy - нужно ли использовать решенную прокси между запросами в 1 потоке
 * @param urlForTestProxy - ссылка для проверки прокси, если в ответе не будет CF, сразу вернет результат. deafault - ссылка, на который нужен запрос.
 * @param isSwapProxyOnError - будет ли сменяться прокси при неудачном решении челенджа. default - true
 * @param selector - Если cmd==request.clickonelement, то решалка попробует нажать на элемент по данному селектору.
 * @param selectortype - тип селектора для selector.
 * @param selector_wait_time - время ожидания селектора. в мс
 * @param click_timeout_raise - будет ли решалка выбрасывать ошибку, если не удалось нажать на элемент. default - false
 * @param waiting_url Если cmd==request.waitforurl, то решалка будет ждать любой запрос, ссылка которая, содержить данную подстроку.
 * @param forceTrigers - будет ли решалка использовать тригеры для отправки запроса. default - false
 * @param trigers - массив тригеров, при срабатывании любого из них, активируется логика решения челенджей cloudflare.
 * @param preferred_challenge - Строка, в котором описан провайдер. Будет применена логика trigers и getOpts
 */
export type FlareSolverParams = {
    server?: string,

    cmd?: "request.get" | "request.post" | "request.enhancedpost" | "request.clickonelement" | "request.waitforurl",
    postData?: string | Buffer,

    preferredChallengeWorker?: IChallengeWorker,

    driver?: "uc" | "gecko",
    manipulator?: "playwright" | "selenium" | "nodriver",

    headfull?: boolean,
    flag?: "headfull" | "ozon" | "cloudflare" | "gatecrasher"
    cookies?: Cookie[],

    useSolvedProxy?: boolean,
    urlForTestProxy?: string,
    isSwapProxyOnError?: boolean | 0 | 1,

    selector?: string,
    /** @deprecated - нужен только для selenium*/
    selectortype?: "xpath" | "css selector" | "id" | "class name",
    selector_wait_time?: number,
    click_timeout_raise?: boolean,

    waiting_url?: string,

    keys_of_local_storage?: string[],

    forceTrigers?: boolean,
    trigers?: Triggers;

    use_headers?: boolean,
    retries?: number
}

export type Impersonate = "chrome99" | "chrome100" | "chrome101" | "chrome104" | "chrome107" | "chrome110" | "chrome116" | "chrome119" | "chrome120" | "chrome99_android" | "edge99" | "edge101" | "safari15_3" | "safari15_5" | "safari17_0" | "safari17_2_ios"

export interface CommandCurlCffi {
    proxy: string,
    link: string,
    method: 'GET' | 'HEAD' | 'POST' | 'PUT' | 'DELETE' | 'CONNECT' | 'OPTIONS' | 'TRACE' | 'PATCH'
    host?: string,
    response_to_json?: boolean,
    get_all_info?: boolean,
    impersonate?: Impersonate,
    cookies?: string,
    body?: { [key: string]: any } | string,
    body_is_json?: boolean,
    headers?: { [key: string]: any },
    akamai?: string,
    ja3?: string,
}

/**
 * @param server - ссылка на апи, указывается для тестирования (http://10.0.4.69:1337/make_request)
 * @param impersonate - fingerprint для эмуляции. В случае указания нескольких значений, будет использовано случайное из них.
 * @param akamai - akamai значение tls фингерпринта
 * @param ja3 - значение метода отпечатков.
 * @param cookies - список кук, которые будут переопределены opts.cookies
 */
export type CurlCffiParams = {
    server?: string,

    impersonate?: Impersonate | Impersonate[],
    akamai?: string,
    ja3?: string,
    cookies?: Cookie[],
    body_is_json?: boolean
}

export type TlsClients = "chrome_103" | "chrome_104" | "chrome_105" | "chrome_106" | "chrome_107" | "chrome_108" | "chrome_109" | "chrome_110" | "chrome_111" | "chrome_112" | "chrome_116_PSK" | "chrome_116_PSK_PQ" | "chrome_117" | "chrome_120" | "chrome_124" | "chrome_131" | "chrome_131_PSK" | "chrome_133" | "chrome_133_PSK" | "safari_15_6_1" | "safari_16_0" | "safari_ipad_15_6" | "safari_ios_15_5" | "safari_ios_15_6" | "safari_ios_16_0" | "safari_ios_17_0" | "safari_ios_15_6" | "firefox_102" | "firefox_104" | "firefox_105" | "firefox_106" | "firefox_108" | "firefox_110" | "firefox_117" | "firefox_120" | "firefox_123" | "firefox_132" | "firefox_133" | "firefox_135" | "opera_89" | "opera_90" | "opera_91" | "okhttp4_android_7" | "okhttp4_android_8" | "okhttp4_android_9" | "okhttp4_android_10" | "okhttp4_android_11" | "okhttp4_android_12" | "okhttp4_android_13" | "zalando_ios_mobile" | "zalando_android_mobile" | "nike_ios_mobile" | "nike_android_mobile" | "cloudscraper" | "mms_ios" | "mms_ios_1" | "mms_ios_2" | "mms_ios_3" | "mesh_ios" | "mesh_ios_1" | "mesh_ios_2" | "mesh_android" | "mesh_android_1" | "mesh_android_2" | "confirmed_ios" | "confirmed_android" | "confirmed_android_7" | "confirmed_android_8" | "confirmed_android_9" | "confirmed_android_10" | "confirmed_android_11" | "confirmed_android_12" | "confirmed_android_13"

export interface CommandTlsClient {
    url: string,
    method: "GET" | "HEAD" | "POST" | "PUT" | "DELETE" | "CONNECT" | "OPTIONS" | "TRACE" | "PATCH"
    params?: { [key: string]: any }
    data?: string,
    hex?: string,
    bytes?: string,
    json?: { [key: string]: any },
    headers?: { [key: string]: any },
    cookies?: Cookie[]
    proxy?: string,

    preset?: TlsClients,
    ja3?: string,
    is_data_bytes?: boolean,
    is_data_hex?: boolean,
    allow_redirects?: boolean,
}

/**
 * @param server - ссылка на апи, указывается для тестирования (http://10.0.4.69:46064/request)
 * @param preset - fingerprint для эмуляции..
 * @param cookies - список кук, которые будут переопределены opts.cookies
 * @param is_data_bytes - Принимаемое и отдаваемое тело должно принимать строку номера байтов, через запятую (0,0,0,156...)
 * @param is_data_hex - Принимаемое и отдаваемое тело должно принимать hex строку
 */
export type TlsClientParams = {
    server?: string,

    preset?: TlsClients | TlsClients[],
    ja3?: string,
    cookies?: Cookie[],
    is_data_bytes?: boolean,
    is_data_hex?: boolean,
    allow_redirects?: boolean,
}

export interface AsyncHTTPXRequestOptsCustom extends AsyncHTTPXRequestOpts {
    flaresolver_params?: FlareSolverParams;
    curlCffi_params?: CurlCffiParams;
    tlsClient_params?: TlsClientParams;
    cookies?: Cookie[];
    user_agent?: string;
    /** Движок, который будет использован для запроса.
     * @param a-parser - запросы будут отправляться через a-parser
     * @param curlCffi - запросы будут отправляться через curlCffi 10.0.4.69:1337
     * @param tlsClient - запросы будут отправляться через tls-client2 10.0.4.69:46064
     */
    engine?: Engine,
    /** Написанная логика обработки ответа.
     @param normal - обычные запросы
     @param flaresolver - будет использована логика решения челенджей cloudflare
    **/
    mode?: Mode,
    botPreset?: BotInfo | BotInfo[],
    json?: { [key: string]: any },
}

export type IChallengeWorker = {
    providerName: string
    error: BanError,
    isChallenge: (data: string, hdr: HeadersType) => 0 | 1
    isBan: (data: string, hdr: HeadersType) => 0 | 1
}

export function validateAsyncHTTPXRequestOptsCustom(opts: AsyncHTTPXRequestOptsCustom, conf: defaultConf): AsyncHTTPXRequestOptsCustom {
    if (!opts.check_content) opts.check_content = []
    if (!opts.parsecodes) opts.parsecodes = conf.parsecodes || { 200: 1 };
    if (!opts.headers) opts.headers = {}
    if (opts.cookies) opts.headers.cookie = CustomCookiesJar.toString(opts.cookies)
    if (opts.user_agent) opts.headers["User-Agent"] = opts.user_agent
    return opts
}

export type Cookie = {
    name: string,
    value: string,
    path?: string,
    domain?: string,
    secure?: string | boolean,
    httpOnly?: string | boolean,
    expiry?: string,
    sameSite?: string
}

export type FieldType = 'textfield' | 'textfieldmulti' | 'textfieldlong' | 'combobox' | 'combobox_search' | 'comboboxmedium' | 'checkbox' | 'checkboxlong';
export type FieldConfigType = [
    fieldType: FieldType,
    fieldLabel: string,
    fieldOptions?: {},
    ...fieldValues: [fieldValue: any, valueTitle: string][] | [string | number]
];
export type editableConf = [
    ...[
        fieldName: string,
        fieldConfig: FieldConfigType
    ][]
];

export type defaultConf = {
    timeout?: number;
    useproxy?: any;
    max_size?: number;
    cache_hours?: number,
    proxyretries?: number;
    requestdelay?: string | number;
    proxybannedcleanup?: number;
    pagecount?: number;
    pagescount?: number;
    itemscount?: number;
    /**
     * *.ru - русские прокси
     * *.ae - арабские прокси
     * *.we - западная европа
     * *.asia - Азия
     * *.baltica - Балтийские прокси
     * *.eu - европа (подобные)
     * *.harvey - для JS_Base_harveynicholscom
     **/
    proxyChecker?: "fineproxy.merged" | "fineproxy.org.ru" | "fineproxy.org" | "motley.crew" | "mobile.proxy" | "iproyal" | "proxy.am.ae" | "proxy.am.we" | "squid.test" | "tor.merged" | "tor.proxy.ae" | "tor.proxy.asia" | "tor.proxy.baltica" | "tor.proxy.eu" | "tor.proxy.harvey" | "tor.proxy.ru" | "tor.proxy";
    parsecodes?: {
        [code: string]: 1 | 0 | boolean;
    };
    debug?: 0 | 1 | boolean;
    queryformat?: string;
    results: {
        flat?: [...field[]];
        arrays?: {
            [arrayName: string]: [
                title: string,
                variables: field[]
            ];
        };
    };
    results_format: string;
    version?: string;
    /** Движок, который будет использован для запроса.
     * @param a-parser - запросы будут отправляться через a-parser
     * @param curlCffi - запросы будут отправляться через curlCffi 10.0.4.69:1337
     * @param tlsClient - запросы будут отправляться через tls-client2 10.0.4.69:46064
     */
    engine?: Engine,
    /** Написанная логика обработки ответа.
     @param normal - обычные запросы
     @param flaresolver - будет использована логика решения челенджей cloudflare
    **/
    mode?: Mode
    force_parse?: boolean;
    [propName: string]: any;
}

export interface BotInfo {
    userAgent: string;
    akamai?: string;
    ja3?: string;
}

export interface CacheItems {
    timestamp: number;
    items: any;
}

export type CustomResponse = {
    success: number;
    headers: HeadersType;
    data: any;
    error: any;
    connInfo?: connInfoType | undefined;
    cookies: Cookie[],
    localStorage?: {}
}

declare function _checkContent(data: any, hdr: HeadersType): boolean | 0 | 1;

type SimpleTrigger = RegExp | string | number
type PositiveTrigger = SimpleTrigger | typeof _checkContent
export type Trigger = PositiveTrigger | [PositiveTrigger]
export type Triggers = Trigger[];

export type connInfoType = {
    [propName: string]: any;
};