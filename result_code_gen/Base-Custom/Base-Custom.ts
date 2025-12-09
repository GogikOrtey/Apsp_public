import { UnsolveChallengeError, FlaresolverError, BanCloudflareError, BanQratorError, BanError, BanServicePipeError } from './Errors';
import { Cookie, AsyncHTTPXRequestOptsCustom, defaultConf, connInfoType, Triggers, Trigger, CustomResponse } from './Types';
import { clone, randInt, updateDelayByProxyUsage } from './Utils';
import { BaseParser, HeadersType, tools } from 'a-parser-types';
import { LEMENA_MONITORINGS, OptsGenerators } from './Constants';
import { ChallengeDetector, CloudflareChallengleWorker, QratorChallengleWorker, ServicePipeChallengleWorker } from "./ChallengeWorker"
import { CustomCookiesJar } from './CustomCookies';
import { Cacher } from './Cache';

export { CustomCookiesJar } from './CustomCookies';
export { presets } from './ChallengeWorker';
export * from './Fields';
export * from './Types';
export * from './Errors';

import * as cheerio from "cheerio";


export class JS_Base_Custom extends BaseParser {
    static defaultConf: defaultConf

    private timer?: NodeJS.Timeout

    declare readonly conf: defaultConf;
    //@ts-ignore
    protected requestdelay: string
    //@ts-ignore
    protected prevrequestdelay: string
    userAgent?: string
    solvedProxy?: string

    async init() {
        await tools.memory.set(`${this.constructor.name}_requestDelay`, clone(this.conf.requestdelay?.toString() || "0").replace(/\s*/g, ''))
    }

    async threadInit() {
        this.requestdelay = await tools.memory.get(`${this.constructor.name}_requestDelay`);
        this.prevrequestdelay = await tools.memory.get(`${this.constructor.name}_requestDelay`);
        if (this.conf.proxyChecker?.startsWith("proxy.am")) {
            this.logger.put("Активировал смену requestdelay, взависимости от трафика")
            this.timer = setInterval(updateDelayByProxyUsage, 2.5 * 60 * 1000, this)
        };
    }

    async threadDestroy() {
        if (this.timer) clearInterval(this.timer)
    }

    async request(
        method: 'GET' | 'HEAD' | 'POST' | 'PUT' | 'DELETE' | 'CONNECT' | 'OPTIONS' | 'TRACE' | 'PATCH',
        url: string,
        urlParams?: {},
        opts?: AsyncHTTPXRequestOptsCustom
    ): Promise<{
        success: number;
        headers: HeadersType;
        data: any;
        error: any;
        connInfo?: connInfoType | undefined;
        cookies: Cookie[]
    }> {
        this.conf.requestdelay = 0;
        if (!opts) opts = {};

        const parseCodes = Object.keys(this.conf.parsecodes || { 200: 1 }).map(Number)

        if (!opts.check_content) opts.check_content = []
        if (!opts.parsecodes) opts.parsecodes = this.conf.parsecodes || { 200: 1 };
        if (!opts.headers) opts.headers = {}
        if (!opts.cookies) opts.cookies = []
        if (!opts.curlCffi_params) opts.curlCffi_params = {}
        if (opts.user_agent) opts.headers["User-Agent"] = opts.user_agent
        if (opts.botPreset) {
            if (Array.isArray(opts.botPreset)) {
                const preset = opts.botPreset[Math.floor(Math.random() * opts.botPreset.length)]
                opts.headers["User-Agent"] = preset.userAgent
                if (preset.akamai) opts.curlCffi_params.akamai = preset.akamai
                if (preset.ja3) opts.curlCffi_params.ja3 = preset.ja3
            } else {
                opts.headers["User-Agent"] = opts.botPreset.userAgent
                if (opts.botPreset.akamai) opts.curlCffi_params.akamai = opts.botPreset.akamai
                if (opts.botPreset.ja3) opts.curlCffi_params.ja3 = opts.botPreset.ja3
            }
        }

        if (!opts.mode) opts.mode = this.conf.mode || "normal"
        switch (opts.mode) {
            case "normal": {
                break;
            }
            case "flaresolver": {
                const response = await this.flaresolverRequest(method, url, urlParams, opts);
                return response;
            }
            default: {
                throw new Error(`Неизвестный режим ${opts.mode}`);
            };
        };

        if (!opts.engine) opts.engine = this.conf.engine || "a-parser"
        switch (opts.engine) {
            case "a-parser": {
                if (opts.cookies.length > 0) opts.headers.Cookie = CustomCookiesJar.toString(opts.cookies)
                opts.proxyretries = 1
                if (opts.json) opts.body = JSON.stringify(opts.json)
                for (let i = 0; i < (this.conf.proxyretries || 10); i++) {
                    await this.customSleep()
                    const response = await super.request(method, url, urlParams, opts) as {
                        success: number;
                        headers: HeadersType;
                        data: any;
                        error: any;
                        connInfo?: connInfoType | undefined;
                        cookies: Cookie[]
                    }

                    if (response.success === 0) {
                        await this.proxy.set(await this.proxy.get())
                        await this.proxy.next()
                        continue
                    }

                    const cookies = CustomCookiesJar.validate(CustomCookiesJar.parse(response.headers["set-cookie"]), new URL(url))
                    this.customCookieJar.addMany(cookies)

                    response.cookies = cookies

                    return response
                }
            }
            case "curlCffi": {
                if (opts.cookies.length > 0) opts.headers.Cookie = CustomCookiesJar.toString(opts.cookies)
                const response = await this.curlCffiRequest(method, url, urlParams, opts);
                return response;
            }
            case "tlsClient": {
                const response = await this.tlsClientRequest(method, url, urlParams, opts);
                return response;
            }
            default:
                throw new Error(`Неизвестный движок ${opts.engine}`)
        }
    }

    processResultsForLemana(results: any) {
        if ((!LEMENA_MONITORINGS?.includes(this.conf.MonitoringUUID)) || results.success == 0) return results
        const fields: any[] = this.conf.formatable.arrays.items.at(1)
        const linkIndex = fields.map(([name, desc]) => name).indexOf("link")
        if (results.items.length > 0) results.items[linkIndex] = results.query
        return results;
    };

    private flaresolverApiRequests = {
        challengeWorker: undefined,
        registerChallenge: async (opts: AsyncHTTPXRequestOptsCustom, solverServer: string) => {
            let registerResponse = await super.request("POST", `${solverServer}/register/challange`, {}, opts);
            if (registerResponse.headers.Status === 530) {
                throw new UnsolveChallengeError()
            }
        },
        privatizeSolver: async (opts: AsyncHTTPXRequestOptsCustom, solverServer: string): Promise<any> => {
            let privateRespone = await super.request("POST", `${solverServer}/privatize/solver`, {}, opts)
            if (privateRespone.headers.Status === 406) {
                this.logger.put("No free solvers, sleeping 5 seconds")
                await this.sleep(5)
            }
            if ([200, 412].includes(privateRespone.headers.Status)) {
                return privateRespone
            }
            if ([404, 428, 500, 597, 520].includes(privateRespone.headers.Status)) {
                await this.flaresolverApiRequests.registerChallenge(opts, solverServer)
                return await this.flaresolverApiRequests.privatizeSolver(opts, solverServer)
            }
            return await this.flaresolverApiRequests.privatizeSolver(opts, solverServer)
        },
        solveChallenge: async (opts: AsyncHTTPXRequestOptsCustom, solverServer: string) => {
            let solveResponse = await super.request("POST", `${solverServer}/solver/challange`, {}, opts);
            await this.proxy.set(await this.proxy.get())
            const solvedData = solveResponse.data.toString()
            if ([404, 428].includes(solveResponse.headers.Status)) throw new FlaresolverError("Challenge не запривачен")

            let allChallengeWorkers = [CloudflareChallengleWorker, QratorChallengleWorker, ServicePipeChallengleWorker]
            if (this.flaresolverApiRequests.challengeWorker) allChallengeWorkers = [this.flaresolverApiRequests.challengeWorker]

            for (let chWorker of allChallengeWorkers) {
                if (solvedData.includes(`${chWorker.providerName} has blocked this request.`)) throw chWorker.error
            }

            if ([500, 597, 520, 503].includes(solveResponse.headers.Status) || solveResponse.success === 0) {
                this.debugger.put(solvedData)
                await this.proxy.next()
                if (typeof opts.flaresolver_params?.isSwapProxyOnError === "boolean" && opts.flaresolver_params?.isSwapProxyOnError) {
                    await this.proxy.next()
                }
                throw new FlaresolverError("Challenge не решен")
            }
            let solution = JSON.parse(solvedData)?.solution
            return { solution, solve_response: solveResponse }
        }
    }

    private async flaresolverRequest(
        method: 'GET' | 'HEAD' | 'POST' | 'PUT' | 'DELETE' | 'CONNECT' | 'OPTIONS' | 'TRACE' | 'PATCH',
        url: string,
        urlParams?: {},
        opts?: AsyncHTTPXRequestOptsCustom
    ): Promise<CustomResponse> {
        if (!opts) opts = {};
        if (!opts.check_content) opts.check_content = []
        if (!opts.parsecodes) opts.parsecodes = this.conf.parsecodes || { 200: 1 };

        // if (method !== "GET" && method !== "POST") throw new NotAllowedMethod(method)

        //Проверка параметров
        if (!opts.flaresolver_params) opts.flaresolver_params = {}
        if (typeof opts.flaresolver_params.useSolvedProxy === "undefined") opts.flaresolver_params.useSolvedProxy = true
        if (typeof opts.flaresolver_params.forceTrigers === "undefined") opts.flaresolver_params.forceTrigers = false
        if (typeof opts.flaresolver_params.cmd === "undefined") opts.flaresolver_params.cmd = "request.get"
        if (!opts.flaresolver_params.trigers) opts.flaresolver_params.trigers = []
        if (opts.flaresolver_params.preferredChallengeWorker) opts.flaresolver_params.trigers = [opts.flaresolver_params.preferredChallengeWorker.isChallenge, ...opts.flaresolver_params.trigers]
        if (!opts.flaresolver_params.server) opts.flaresolver_params.server = `http://10.0.4.215:9000`
        if (typeof opts.flaresolver_params.isSwapProxyOnError === "undefined") opts.flaresolver_params.isSwapProxyOnError = true

        const parseCodes = clone(opts.parsecodes || this.conf.parsecodes || { 200: 1 })

        for (let i = 0; i < (opts.flaresolver_params.retries || 20); i++) {
            if (opts.flaresolver_params.useSolvedProxy && this.solvedProxy) await this.proxy.set(this.solvedProxy)
            if (!opts.flaresolver_params.forceTrigers) {
                const clonedOpts = clone(opts)
                clonedOpts.flaresolver_params = {}
                clonedOpts.mode = "normal"
                clonedOpts.parsecodes[403] = 1
                clonedOpts.parsecodes[401] = 1
                let res = await this.request(method, clonedOpts.flaresolver_params.urlForTestProxy || url, urlParams, clonedOpts)
                try {
                    const trigger = opts.flaresolver_params.trigers.find(trigger => this.processTrigger(trigger, res.data, res.headers))
                    if (!clonedOpts.flaresolver_params.urlForTestProxy) {
                        if (typeof trigger === "undefined") {
                            if (parseCodes[res.headers.Status] !== 1) {
                                this.logger.put(`Invalid status code 🫤 - ${res.headers.Status}`)
                                await this.proxy.set(await this.proxy.get())
                                await this.proxy.next()
                                continue
                            };
                            this.logger.put("No triggers, returning response")
                            this.solvedProxy = await this.proxy.get()
                            return res
                        } else this.logger.put(`Trigger<${trigger}> was triggered🤓. Request will be send via GateCrasher`)
                    }
                } catch (e) {
                    continue
                }
                await this.proxy.set(await this.proxy.get(), true)
            }
            if (opts.cookies && !opts.flaresolver_params.cookies) opts.flaresolver_params.cookies = opts.cookies

            const proxy = opts.use_proxy === 0 ? undefined : await this.parseProxy()

            const fsOpts = OptsGenerators.getOptsForCF(url, urlParams || {}, opts, proxy);
            this.debugger.put(fsOpts)//@ts-ignore

            await this.flaresolverApiRequests.registerChallenge(fsOpts, opts.flaresolver_params.server)
            await this.flaresolverApiRequests.privatizeSolver(fsOpts, opts.flaresolver_params.server)

            let solution, solve_response
            try {
                await this.customSleep()
                let res = await this.flaresolverApiRequests.solveChallenge(fsOpts, opts.flaresolver_params.server)
                solution = res.solution
                solve_response = res.solve_response
            } catch (e) {
                if (e instanceof BanError) {
                    this.logger.put(`${e.provider} забанил прокси`)
                    await this.proxy.set(await this.proxy.get());
                    await this.proxy.ban()
                    await this.proxy.next()
                    opts.cookies = []
                    opts.flaresolver_params.cookies = []
                }
                continue
            }

            //@ts-ignore
            if (!this.ua) this.ua = solution.userAgent;
            if (!this.userAgent) this.userAgent = solution.userAgent
            this.debugger.put(solution.cookies)
            this.customCookieJar.addMany(solution.cookies)
            this.debugger.put(this.customCookies)
            if (opts.flaresolver_params.useSolvedProxy) this.solvedProxy = await this.proxy.get()
            let data = solution?.response
            if (data.includes("json-formatter-container")) {
                const $ = cheerio.load(data)
                const json = $("pre")
                data = json.text()
            }
            return { ...solve_response, cookies: solution?.cookies, data, headers: { ...solution?.headers, Status: solution?.status || 200, Challanged: true, Challenged: true }, localStorage: solution?.local_storage || {} }
        }
        throw Error("Неудачный запрос")
    }

    private async curlCffiRequest(
        method: 'GET' | 'HEAD' | 'POST' | 'PUT' | 'DELETE' | 'CONNECT' | 'OPTIONS' | 'TRACE' | 'PATCH',
        url: string,
        urlParams?: {},
        opts?: AsyncHTTPXRequestOptsCustom
    ): Promise<CustomResponse> {
        if (!opts) opts = {};
        if (!opts.check_content) opts.check_content = []
        if (!opts.parsecodes) opts.parsecodes = this.conf.parsecodes || { 200: 1 };
        if (!opts.curlCffi_params) opts.curlCffi_params = {}
        if (!opts.curlCffi_params.server) opts.curlCffi_params.server = this.threadId % 2 == 0 ? `http://10.0.4.69:1337/make_request` : `http://10.0.4.70:1337/make_request`

        for (let i = 0; i < 20; i++) {
            await this.customSleep()
            if (!opts.cookies) opts.curlCffi_params.cookies = opts.cookies
            let curlCffiOpts = OptsGenerators.getOptsForCurlCffi(method, url, urlParams || {}, opts, await this.proxy.get())
            this.debugger.put(curlCffiOpts)
            let _url = new URL(url)
            if (urlParams && Object.entries(urlParams).length > 0) {
                Object.entries(urlParams).map(([k, v]) => _url.searchParams.append(k, v as string))
            }
            this.logger.put(`${method}(${i + 1})`, "(via curlCffi) ", _url.href)
            let response = await super.request("POST", opts.curlCffi_params.server, {}, curlCffiOpts);
            if (!Boolean(response.success)) {
                await this.proxy.set(await this.proxy.get())
                await this.proxy.next()
                continue
            }
            const solution = JSON.parse(response.data.toString())
            const data = solution?.result || solution?.detail
            const headers = { ...solution?.headers, Status: response?.headers?.Status || 200 }
            //@ts-ignore
            const trigger = (opts.check_content || []).find(trigger => this.processTrigger(trigger, data, headers, true))
            if (typeof trigger !== "undefined") {
                this.logger.put(`Content mismatch 🫤 - ${trigger}`)
                await this.proxy.set(await this.proxy.get())
                await this.proxy.next()
                continue
            }
            await this.proxy.set(await this.proxy.get())
            const cookies_headers = CustomCookiesJar.validate(CustomCookiesJar.parse(solution?.headers?.["set-cookie"]), new URL(url))
            this.customCookieJar.addMany(cookies_headers)
            const cookies = CustomCookiesJar.validate(Object.entries(solution?.cookies || {}).map(([k, v]) => ({ name: k.toString(), value: (v || "").toString() })), new URL(url))
            this.customCookieJar.addMany(cookies)
            return { ...response, cookies: Array.from(new Set([...cookies, ...cookies_headers])), data, headers, }
        }
        throw Error("Неудачный запрос")
    }

    private async tlsClientRequest(
        method: "GET" | "HEAD" | "POST" | "PUT" | "DELETE" | "CONNECT" | "OPTIONS" | "TRACE" | "PATCH",
        url: string,
        urlParams?: {},
        opts?: AsyncHTTPXRequestOptsCustom
    ): Promise<CustomResponse> {
        if (!opts) opts = {};
        if (!opts.check_content) opts.check_content = []
        if (!opts.parsecodes) opts.parsecodes = this.conf.parsecodes || { 200: 1 };
        if (!opts.tlsClient_params) opts.tlsClient_params = {}
        if (!opts.tlsClient_params.server) opts.tlsClient_params.server = this.threadId % 2 == 0 ? `http://10.0.4.69:46064/request` : `http://10.0.4.70:46064/request`

        const parseCodes = clone(opts.parsecodes || this.conf.parsecodes || { 200: 1 })

        for (let i = 0; i < 20; i++) {
            await this.customSleep();
            if (!opts.cookies) opts.tlsClient_params.cookies = opts.cookies
            let tlsClientOpts = OptsGenerators.getOptsForTlsClient(method, url, urlParams || {}, opts, await this.proxy.get())
            this.debugger.put(tlsClientOpts)
            let _url = new URL(url)
            if (urlParams && Object.entries(urlParams).length > 0) {
                Object.entries(urlParams).map(([k, v]) => _url.searchParams.append(k, v as string))
            }
            this.logger.put(`${method}(${i + 1})`, "(via tlsClient) ", _url.href)
            let response = await super.request("POST", opts.tlsClient_params.server, {}, tlsClientOpts);
            if (response.success === 0 || response.headers.Status === 500) {
                if (new Date().getMinutes() % 15 === 0) {
                    this.logger.put(`Propably TlsClient is restarting.`)
                    await this.customSleep(60);
                    continue;
                }
                // await this.proxy.set(await this.proxy.get())
                await this.proxy.next()
                continue;
            }
            await this.proxy.set(await this.proxy.get())
            const solution = JSON.parse(response.data.toString())
            const data = solution?.body
            const headers = { ...solution?.headers, Status: solution?.status || 200 }
            //@ts-ignore
            const trigger = (opts.check_content || []).find(trigger => this.processTrigger(trigger, data, headers, true))
            if (typeof trigger !== "undefined") {
                this.logger.put(`Content mismatch 🫤 - ${trigger}`)
                await this.proxy.set(await this.proxy.get())
                await this.proxy.next()
                continue
            }
            if (parseCodes[(solution?.status || 200)] !== 1) {
                this.logger.put(`Invalid status code 🫤 - ${solution?.status}`)
                await this.proxy.set(await this.proxy.get())
                await this.proxy.next()
                continue
            };
            this.customCookieJar.addMany(solution?.cookies || [])
            return { ...response, cookies: solution?.cookies, data, headers, }
        }
        throw Error("Неудачный запрос")
    }

    getFromCache(params: object, hours: number = 18): null | any {
        const cacher = new Cacher(this.constructor.name, hours, params);
        return cacher.cache;
    }

    saveToCache(params: object, items: any): void {
        const cacher = new Cacher(this.constructor.name, 18, params);
        cacher.cache = items;
    }

    private processTrigger(trigger: Trigger, data: any, headers: HeadersType, negate: boolean = false): boolean {
        try {
            if (Array.isArray(trigger)) {
                return typeof trigger.find(trigger => this.processTrigger(trigger, data, headers, !negate)) !== "undefined"
            }
            if (trigger instanceof RegExp) return trigger.test(data) !== negate
            switch (typeof trigger) {
                case "function":
                    return Boolean(trigger(data.toString(), headers)) !== negate
                case "number":
                    return Boolean(headers.Status === trigger) !== negate
                case "string":
                    return data.includes(trigger) !== negate
                default:
                    return false;
            }
        } catch (e) {
            if (e instanceof BanError) {
                this.customCookies = [];
                this.proxy.ban().then(() => this.logger.put(`${e.provider} ban this ip. Banning proxy. Need to set proxybannedcleanup`))
                throw e
            } else {
                this.logger.put("Ошибка при проверке триггеров", e)
            }
            return false
        }
    }

    private async parseProxy() {
        const proxy = await this.proxy.get()
        let result: { url: string, username?: string, password?: string } = { url: proxy }
        const execProxy = /(?:(?<schema>socks\d|http):\/\/)?(?:(?<username>[^:@]+):(?<password>[^@:]+)@)?(?<url>.+:\d{1,5})/.exec(proxy)
        if (execProxy && execProxy.groups) {
            const { schema, username, password, url } = execProxy.groups //@ts-ignore
            result = { url, username, password }
            result.url = `${schema || "http"}://${url}`
        } else {
            throw new Error("Не удалось спарсить прокси")
        }
        return result
    }

    private customCookiesList: Cookie[] = []
    customCookieJar: CustomCookiesJar = new CustomCookiesJar(this.customCookiesList)

    get customCookies(): Cookie[] {
        return this.customCookieJar.cookies
    }

    set customCookies(cookies: Cookie[]) {
        this.customCookieJar.cookies = cookies
    }

    set requestDelay(delay: string) {
        this.requestdelay = delay
        if (this.requestdelay !== this.prevrequestdelay) {
            console.log(`Сменил requestdelay: ${this.requestdelay}`)
            this.logger.put(`Сменил requestdelay: ${this.requestdelay}`)
        }
        this.prevrequestdelay = delay
    }

    /**
     * Вложеные методы срабатывают только при this.conf.debug === true.
     */
    debugger = {
        /**
         * Вывод информации, при помощи this.logger.put. Имеет автоконвертацию объектов JSON.stringify.
         * @param message: any[]
         */
        put: (...message: any[]) => {
            if (typeof this.conf.debug !== "undefined" && this.conf.debug) {
                message = message.map(m => {
                    try {
                        if (typeof m == 'object') {
                            m = JSON.stringify(m)
                        }
                    } catch {

                    }
                    return m
                })
                this.logger.put(...message)
            }
        },
        /**
         * Вывод информации, при помощи this.logger.putHTML
         * @param html
         */
        putHTML: (html: string | Buffer) => {
            if (typeof this.conf.debug !== "undefined" && this.conf.debug) {
                this.logger.putHTML(html)
            }
        }, //@ts-ignore
        putImage: (image: Buffer, { type, description }) => {
            if (typeof this.conf.debug !== "undefined" && this.conf.debug) {
                this.logger.putImage(image)
            }
        }
    }


    private async customSleep(timeToSleep = 0) {
        if (timeToSleep === 0) {
            if (typeof this.requestdelay === "string" && /\d+,\d+/g.test(this.requestdelay)) {
                const [n1, n2] = this.requestdelay.split(',')
                timeToSleep = randInt(+n1, +n2)
            } else if (typeof +this.requestdelay === "number" && +this.requestdelay > 0) {
                timeToSleep = +this.requestdelay
            }
        }
        this.logger.put(`Сплю ${timeToSleep} секунд перед запросом. 😪`)
        await this.sleep(timeToSleep)

    }

    /**
     * Данный метод нужен для автоматического выставления хоста в ссылке, если ее нет. Реализованно через URL API в js
     * @param href Адрес ссылки
     * @param host Хост, который должен быть в ссылке
     * @param [isReplaceHost=false] Нужно ли заменять хост в ссылке, если href пришел с хостом
     * @returns Итоговую ссылку.
     */
    createFullLink(href: string, host: string, isReplaceHost: boolean = false) {
        const url = new URL(href, host)
        if (url.host !== host && isReplaceHost) {
            url.host = (new URL(host)).host
        }
        return url.href
    }
}

declare global {
    interface String {
        formatPrice(separator?: string): string;
    }
}

String.prototype.formatPrice = function (separator: string = "."): string {
    return this.replace(new RegExp(`[^0-9${separator}]+`, "g"), "").replace(separator, ".").match(/\d+(?:\.\d{0,2})?/)?.shift() || ""
}