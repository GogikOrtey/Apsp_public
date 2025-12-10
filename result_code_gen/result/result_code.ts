import { getDefaultConf, defaultEditableConf, defaultOpts, getCacher } from "../Base-Custom/Constants";
import { AsyncHTTPXRequestOptsCustom, defaultConf, editableConf, Item } from "../Base-Custom/Types";
import { InvalidLinkError, NotFoundError } from "../Base-Custom/Errors";
import { JS_Base_Custom } from "../Base-Custom/Base-Custom";
import { getTimestamp } from "../Base-Custom/Utils";
import { SetType, tools } from "a-parser-types";
import { Cacher } from "../Base-Custom/Cache";
import {
    toArray, isBadLink,
    name, stock, link, price, oldPrice, article, brand, imageLink, timestamp
} from "../Base-Custom/Fields"
import * as cheerio from "cheerio";

//#region Кастомные типы данных
type ResultItem = Item<typeof fields>

//#region Константы
const fields = {
    name, stock, link, price, oldPrice, article, brand, imageLink, timestamp
}

const HOST = "https://hb-shop.by"

export class JS_Base_hbshopby extends JS_Base_Custom {
    static defaultConf: defaultConf = {
            ...getDefaultConf(toArray(fields), "ζ", [isBadLink]),
            parsecodes: { 200: 1, 404: 1 },
            proxyChecker: "tor.proxy.ru",
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
    

    //#region Парсинг товара
    async parseCard(set: SetType, cacher: Cacher<ResultItem[]>) {
        let items: ResultItem[] = []

        const data = await this.makeRequest(set.query);
        const $ = cheerio.load(data);

        const name = $("#modal_review > .modal__window > .modal__body > .modal__desc > .product-small.nohover > .product-small__body > .product-small__header > .product-small__title").text()?.trim()
		const stock = $("#swiper_tovar_similar > .swiper-container > .swiper-wrapper > .swiper-slide > .product > .product__shorts.product-shorts > .product-shorts__item > span").text()?.includes("В наличии") ? "InStock" : "OutOfStock"
		const link = set.query
		const price = $(".tovar__action-price.price > .new > span")?.first().text()?.trim().formatPrice()
		const oldPrice = $("html > body.template.template--tovar > .template__body.container > main.template__main > .section > .tovar > .tovar__info > .tovar__action-price__wrapper > .tovar__action-price.price > .old > span")?.first().text()?.trim().formatPrice()
		const article = $(".pagetitle__subtitle")?.first()?.text()?.trim()?.split(": ")?.at(1)?;
		const brand = $("#tab_chars > table tr:has(td:contains("Бренд")) > td:nth-child(2)")?.first().text()?.trim()
		const imageLink = $("#swiper_tovar_gallery_1 > .gallery__top > .swiper-container > .swiper-wrapper > .swiper-slide > a.tovar__gallery-item").first()?.attr("href")?.trim()?.includes(HOST) ? $("#swiper_tovar_gallery_1 > .gallery__top > .swiper-container > .swiper-wrapper > .swiper-slide > a.tovar__gallery-item").first()?.attr("href")?.trim()?.replace(HOST + "/assets/", HOST) : ""
        const timestamp = getTimestamp()

        const item: ResultItem = {
            name, stock, link, price, oldPrice, article, brand, imageLink, timestamp
        }
        items.push(item);

        cacher.cache = items
        return items;
    }

    //#region Выполнение запроса
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
}

// Код сгенерирован APSP v0.1
// Дата: 10 Дек 2025
// © BrandPol