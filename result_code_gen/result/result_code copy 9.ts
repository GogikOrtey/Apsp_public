import { getDefaultConf, defaultEditableConf, defaultOpts, getCacher } from "../Base-Custom/Constants";
import { AsyncHTTPXRequestOptsCustom, defaultConf, editableConf, Item } from "../Base-Custom/Types";
import { InvalidLinkError, NotFoundError } from "../Base-Custom/Errors";
import { JS_Base_Custom } from "../Base-Custom/Base-Custom";
import { getTimestamp } from "../Base-Custom/Utils";
import { SetType, tools } from "a-parser-types";
import { Cacher } from "../Base-Custom/Cache";
import {
    toArray, isBadLink,
    name, stock, imageLink, article, category, price, breadCrumbs, weight, width, link, timestamp
} from "../Base-Custom/Fields"
import * as cheerio from "cheerio";

//#region Кастомные типы данных
type ResultItem = Item<typeof fields>

//#region Константы
const fields = {
    name, stock, imageLink, article, category, price, breadCrumbs, weight, width, link, timestamp
}

const HOST = "https://makitaclub.ru"

export class JS_Base_makitaclubru extends JS_Base_Custom {
    static defaultConf: defaultConf = {
            ...getDefaultConf(toArray(fields), "ζ", [isBadLink]),
            parsecodes: { 200: 1, 404: 1 },
            proxyChecker: "fineproxy.org",
            requestdelay: "3,5",
            engine: "a-parser",
            mode: "normal",
        };

    static editableConf: editableConf = [
        ...defaultEditableConf
    ];

    //#region Точка входа
    async parse(set: SetType, results: { [key: string]: any }) {
        if (!set.type || set.type === "none") set.type = "page";
        if (!set.region || set.region === "none") set.region = "";
        try {
            switch (set.type) {
                case "page": {
                    if (!set.page || set.page === "none") set.page = 1;
                    await this.parsePage(set);
                    results.success = 1;
                    break;
                }
                case "card": {
                    const cacher = getCacher<ResultItem>(this, set)
                    let items = cacher.cache || await this.parseCard(set, cacher);
                    items.forEach(item => results.items.addElement(item));
                    results.success = 1;
                    break;
                }
                default:
                    this.logger.put("Указан неверный тип сбора")
                    results.success = 0;
            }
        } catch (e: any) {
            if (e instanceof NotFoundError || e instanceof InvalidLinkError) {
                this.logger.put(e.message);
                results.isBadLink = 1;
                results.success = 1;
            } else {
                this.logger.put(`${e.name} >> ${e.message}   ${set.query}  type - ${set.type} page ${set.page} }`);
                results.success = 0;
            }
        }
        return results;
    }

    //#region Парсинг поиска
        async parsePage(set: SetType) {
        let url = new URL(`${HOST}/`);
        url.searchParams.set('s', set.query);
        url.searchParams.set('post_type', 'product');
        if (set.page && Number(set.page) > 1) {
          url.pathname = `/page/${set.page}/`;
        }

        const data = await this.makeRequest(url.href)
        const $ = cheerio.load(data)

        if (set.page === 1) {
            let totalPages = Math.max(...$('nav.woocommerce-pagination .page-numbers').get().map(item => +$(item).text().trim()).filter(Boolean))
            this.debugger.put(`totalPages = ${totalPages}`)
            for (let page = 2; page <= Math.min(totalPages, +this.conf.pagesCount); page++) {
                this.query.add({ ...set, query: set.query, type: "page", page: page, lvl: 1 });
            }
        }

        let products = $(".products .product-card a.stretched-link[href]")
        if (products.length == 0) {
            this.logger.put(`По запросу ${set.query} ничего не найдено`)
            throw new NotFoundError()
        }
        products.slice(0, +this.conf.itemsCount).each((i, product) => {
            let link = $(product)?.attr('href')
            this.query.add({ ...set, query: link, type: "card", lvl: 1 })
        })
    }

    //#region Парсинг товара
    async parseCard(set: SetType, cacher: Cacher<ResultItem[]>) {
        let items: ResultItem[] = []

        const data = await this.makeRequest(set.query);
        const $ = cheerio.load(data);

        const name = $("h1.product_title.entry-title").text().trim()
        const stock = $("form.cart button.single_add_to_cart_button, form.cart .single_add_to_cart_button").text().trim()?.includes("В корзину") ? "InStock" : "OutOfStock"
        const imageLink = $(".woocommerce-product-gallery__wrapper img.wp-post-image").attr("data-src") || $(".woocommerce-product-gallery__wrapper img.wp-post-image").attr("src") || ""
        const article = $(".product_meta .sku_wrapper .sku").first().text().trim()
        const category = $(".product_meta .posted_in a[rel='tag']").first().text().trim()
        const price = $(".summary .price .woocommerce-Price-amount").first().text().trim()?.replace(/,/g, ".")?.replace(/[^\d.]/g, "")
        const breadCrumbs = $(".breadcrumbs .woocommerce-breadcrumb").first().text().trim()?.replace(/\s*\/\s*/g, " / ")
        const weight = $("table.woocommerce-product-attributes tr:contains(\"Вес\") td.woocommerce-product-attributes-item__value").first().text().trim()?.replace(/,/g, ".")
        const width = $("table.woocommerce-product-attributes tr:contains(\"Ширина\") td.woocommerce-product-attributes-item__value").first().text().trim()
        const link = set.query;
        const timestamp = getTimestamp()

        const item: ResultItem = {
            name, stock, imageLink, article, category, price, breadCrumbs, weight, width, link, timestamp
        }
        items.push(item);

        // Отладочный вывод всех полей
        if (this.conf.debug) items.forEach(elem => { Object.entries(elem).forEach(([key, value]) => { this.debugger.put(`🟩 ${key} = ${value}`) }) });

        cacher.cache = items
        return items;
    }
    

    //#region Выполнение запроса
    async makeRequest(url: string, urlPrams = {}) {
        const opts: AsyncHTTPXRequestOptsCustom = {
            ...defaultOpts,
            engine: this.conf.engine,
            mode: this.conf.mode,
        };
        this.debugger.put(opts)

        const { success, headers, data } = await this.request("GET", url, urlPrams, opts);
        this.debugger.put(data)

        if (!success || typeof data !== "string") throw new Error("Неудачный запрос");
        if (headers.Status === 404) throw new NotFoundError();

        return data;
    }
}

// Код сгенерирован Auto-gen parsers v1.0
// Дата: 30 Дек 2025
// © BrandPol