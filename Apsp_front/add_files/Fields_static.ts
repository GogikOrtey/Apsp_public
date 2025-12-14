import { field } from "./Types";

//#region Flat поля
// export const isBadLink: field = ['isBadLink', 'Плохая ссылка (404 или невалидная)']
// //#endregion

//#region Базовые поля
/** ["name", "Наименование товара"] valid */
export const name: field = ['name', 'Наименование товара'];
/** ["link", "Ссылка на товар"] */
export const link: field = ['link', 'Ссылка на товар'];
/** ["price", "Цена"] */
export const price: field = ['price', 'Цена'];
/** ["oldprice", "Старая цена"] */
export const oldprice: field = ['oldprice', 'Старая цена'];
/** ["stock", "Наличие товара"] */
export const stock: field = ['stock', 'Наличие товара'];
/** ["timestamp", "Дата и время сбора данных"] */
export const timestamp: field = ['timestamp', 'Дата и время сбора данных'];
// //#endregion;

// //#region Общие характеристики
// /** ["allCharacteristics", "Все характеристики товара"]
//  * 
//  * данные должны быть вот в таком формате: "key==value||key2==value2||..."
//  */
// export const allCharacteristics: field = ["allCharacteristics", "Все характеристики товара"]
/** ["brand", "Бренд"] valid */
export const brand: field = ['brand', 'Бренд'];
/** ['length', 'Длина'] */
export const length: field = ['length', 'Длина'];
/** ['width', 'Ширина'] */
export const width: field = ['width', 'Ширина'];
/** ['height', 'Высота'] */
export const height: field = ['height', 'Высота'];
// /** ["color", "Цвет товара"] */
// export const color: field = ['color', 'Цвет товара'];
// /** ["size", "Размер товара"] */
// export const size: field = ['size', 'Размер товара'];
// /** ["volume", "Объём товара"] valid */
// export const volume: field = ['volume', 'Объём товара'];
// /** ["currency", "Валюта"] */
// export const currency: field = ['currency', 'Валюта'];
// /** ["region", "Регион"] */
// export const region: field = ['region', 'Регион'];
// /** ["category", "Категория"] */
// export const category: field = ['category', 'Категория'];
// /** ["categories", "Категории"] */
// export const categories: field = ['categories', 'Категории'];
// /** ["diameter", "Диаметр"] */
// export const diameter: field = ['diameter', 'Диаметр'];
// /** ["uom", "Единица измерения"] */
// export const uom: field = ['uom', 'Единица измерения'];
// /** ['series', 'Серия'] */
// export const series: field = ['series', 'Серия'];
// /** ['uom_count', 'Количество единиц измерения'] */
// export const uom_count: field = ['uom_count', 'Количество единиц измерения'];
// /** ["breadCrumbs", "Поисковая цепочка"] */
// export const breadCrumbs: field = ['breadCrumbs', 'Поисковая цепочка'];
// /** ["domain", "Доменное имя"] */
// export const domain: field = ['domain', 'Доменное имя']
// //#endregion

//#region Идентификаторы
/** ["article", "Артикул"] valid */
export const article: field = ['article', 'Артикул'];
/** ["product_id", "Код товара"] valid */
export const product_id: field = ['product_id', 'Код товара'];
/** ['partNumber', 'Партномер (артикул производителя)'] */
// export const partNumber: field = ['partNumber', 'Партномер (артикул производителя)'];
// /** ['marketArticle', 'Артикул маркетплейса'] */
// export const marketArticle: field = ['marketArticle', 'Артикул маркетплейса'];
// /** ['oem', 'OEM-номер'] */
// export const oem: field = ['oem', 'OEM-номер']
/** ["barcode", "Штрихкод"] */
export const barcode: field = ['barcode', 'Штрихкод'];
/** ["manufacturer", "Производитель"] valid */
export const manufacturer: field = ['manufacturer', 'Производитель'];
// /** ["ean", "Международный артикул"] */
// export const ean: field = ["ean", "Международный артикул"];
// /** ["skuArticle", "Внутренний артикул (YM)"] */
// export const skuArticle: field = ["skuArticle", "Внутренний артикул (YM)"]
// //#endregion

// //#region Доп информация о товаре
// /** ["price_discount", "Акционная цена"] */
// export const price_discount: field = ['price_discount', 'Акционная цена'];
// /** ["card_price", "Цена по дисконтной карте"]*/
// export const card_price: field = ["card_price", "Цена по дисконтной карте"]
// /** ["cashback", "Кешбек \ Бонусы"]*/
// export const cashback: field = ["cashback", "Кешбек \ Бонусы"]
// /** ["price_per_unit", "Цена за единицу"] */
// export const price_per_unit: field = ["price_per_unit", "Цена за единицу"]
// /** ["address", "Адрес магазина"] */
// export const address: field = ['address', 'Адрес магазина'];
// /** ["shop", "Название магазина"] */
// export const shop: field = ['shop', 'Название магазина'];
// /** ["seller", "Продавец"] valid */
// export const seller: field = ['seller', 'Продавец'];
// /** ["seller_rating", "Рейтинг товара / Кол-во звездочек"] */
// export const seller_rating: field = ['seller_rating', 'Рейтинг товара / Кол-во звездочек'];
// /** ["rawStock", "Статус товара как на сайте"] */
// export const rawStock: field = ['rawStock', 'Статус товара как на сайте'];
// /** ["availableCount", "Кол-во товара в наличии"] */
// export const availableCount: field = ['availableCount', 'Кол-во товара в наличии'];
// /** ["ordersCount", "Количество заказов"] */
// export const ordersCount: field = ['ordersCount', 'Количество заказов'];
// /** ["rating", "Рейтинг товара / Кол-во звездочек"] */
// export const rating: field = ['rating', 'Рейтинг товара / Кол-во звездочек'];
// /** ["reviewsCount", "Количество отзывов"] */
// export const reviewsCount: field = ['reviewsCount', 'Количество отзывов'];
// /** ["description", "Описание товара"] */
// export const description: field = ['description', 'Описание товара'];
// /** ["promotionDate", "Дата окончания действия акции"] */
// export const promotionDate: field = ['promotionDate', 'Дата окончания действия акции'];
// /** ["imageLink", "Ссылка на фото товара"] */
// export const imageLink: field = ['imageLink', 'Ссылка на фото товара'];
// /** ["imagesLinks", "Ссылки на фото товара"] */
// export const imagesLinks: field = ['imagesLinks', 'Ссылки на фото товара'];
// //#endregion

// //#region Доп характеристики о товаре
// /** ['material', "Материал"] */
// export const material: field = ['material', "Материал"]
// /** ["vat", "Признак включен ли НДС в указанную цену"] */
// export const vat: field = ['vat', 'Признак включен ли НДС в указанную цену'];
// /** ["taste", "Признак вкуса для животных"] */
// export const taste: field = ['taste', 'Признак вкуса для животных'];
// /** ["deliveryDays", "Срок доставки в днях"] */
// export const deliveryDays: field = ['deliveryDays', 'Срок доставки в днях'];
// /** ["pickupDays", "Срок доставки в пвз в днях"] */
// export const pickupDays: field = ['pickupDays', 'Срок доставки в пвз в днях'];
// /** ["deliveryDate", "Дата доставки"] */
// export const deliveryDate: field = ['deliveryDate', 'Дата доставки'];
// /** ["pickupDate", "Дата доставки в пвз в днях"] */
// export const pickupDate: field = ['pickupDate', 'Дата доставки в пвз в днях'];
// /** ["equipment", "Комплектация и измерения/кол-во товаров"] */
// export const equipment: field = ['equipment', 'Комплектация и измерения/кол-во товаров'];
// /** ["packaging", "Упаковка"] */
// export const packaging: field = ['packaging', 'Упаковка'];
// /** ["releaseForm", "Форма выпуска(мазь,пилюли)"] */
// export const releaseForm: field = ['releaseForm', 'Форма выпуска(мазь,пилюли)'];
// /** ["collection", "Коллекция товара"] */
// export const collection: field = ['collection', 'Коллекция товара'];
// /** ["availability", "Статус товара"] */
// export const availibility: field = ['availibility', 'Статус товара'];
// /** ["weight", "Вес товара"] */
// export const weight: field = ['weight', 'Вес товара'];
// /** ["kcal_100", "Пищевая ценность на 100 г"] */
// export const kcal_100: field = ['kcal_100', 'Пищевая ценность на 100 г'];
// /** ["deliveryPrice", "Стоимость доставки"] */
// export const deliveryPrice: field = ['deliveryPrice', 'Стоимость доставки'];
// /** ["deliveryAddress", "Адрес доставки"] */
// export const deliveryAddress: field = ['deliveryAddress', 'Адрес доставки'];
// /** ["model", "Модель"] */
// export const model: field = ['model', 'Модель'];
// /** ["dosage", "Дозировка лекарства"] */
// export const dosage: field = ['dosage', 'Дозировка лекарства'];
// /** ["aromaName", "Название аромата"] */
// export const aromaName: field = ['aromaName', "Аромат"];
// /** ["count", "Кол-во товара в упаковке"] */
// export const count: field = ['count', "Кол-во товара в упаковке"];
// /** ["users", "Кол-во пользователей"] */
// export const users: field = ["users", "Кол-во пользователей"]
// //#endregion

// //#region Книги
// /** ["bookType", "Тип книги"] valid */
// export const bookype: field = ['bookType', 'Тип книги'];
// /** ["isbn", "Международный стандартный книжный номер"] valid */
// export const isbn: field = ['isbn', 'Международный стандартный книжный номер'];
// /** ['issn', 'ISSN'] */
// export const issn: field = ['issn', 'ISSN']
// /** ['coverType', 'Тип обложки'] */
// export const coverType: field = ['coverType', 'Тип обложки']
// /** ['publishYear', 'Год выпуска'] */
// export const publishYear: field = ['publishYear', 'Год выпуска']
// /** ['pagesCount', 'Количество страниц'] */
// export const pages: field = ['pagesCount', 'Количество страниц']
// /** ['publisher', 'Издательство'] */
// export const publisher: field = ['publisher', 'Издательство']
// /** ['author', 'Автор'] */
// export const author: field = ['author', 'Автор']
// //#endregion

// //#region Юридические данные
// /** ["shopLink", "Ссылка на магазин"] */
// export const shopLink: field = ['shopLink', 'Ссылка на магазин'];
// /** ["sellerLink", "Ссылка на продавца"] */
// export const sellerLink: field = ['sellerLink', 'Ссылка на продавца'];
// /** @deprecated - Используй supplierName
//  * ['supplierName', 'Юридическое название продавца'] */
// export const sellerName: field = ['supplierName', 'Юридическое название продавца']
// /** ['supplierName', 'Юридическое название продавца'] */
// export const supplierName: field = ['supplierName', 'Юридическое название продавца']
// /** ['sellerINN', 'ИНН продавца'] */
// export const sellerINN: field = ['sellerINN', 'ИНН продавца']
// /** ['sellerOgrn', 'ОГРН/ОГРНИП продавца'] */
// export const sellerORGN: field = ['sellerOgrn', 'ОГРН/ОГРНИП продавца']
// /** ['sellerAddress', 'Адрес продавца'] */
// export const sellerAddress: field = ['sellerAddress', 'Адрес продавца']
// //#endregion

// //#region Мобильные телефоны
// /** ["ram", "Объем оперативной памяти"] */
// export const ram: field = ['ram', 'Объем оперативной памяти']
// /** ["rom", "Объем постоянной памяти"] */
// export const rom: field = ['rom', 'Объем постоянной памяти']
// //#endregion

// //#region Электроинструмент
// /** ["voltage", "Напряжение (В)"] */
// export const voltage: field = ['voltage', "Напряжение (В)"]
// /** ["torque", "Максимальный крутящий момент (Н·м)"] */
// export const torque: field = ['torque', "Максимальный крутящий момент (Н·м)"]
// /** ["battery_capacity", "Емкость аккумулятора"] */
// export const battery_capacity: field = ['battery_capacity', "Емкость аккумулятора"]
// /** ["speeds_count", "Количество скоростей"] */
// export const speeds_count: field = ['speeds_count', "Количество скоростей"]
// /** ["bullet_diameter", "Диаметр патрона"] */
// export const bullet_diameter: field = ['bullet_diameter', "Диаметр патрона"];
// /** ["disk_diameter", "Диаметр диска (мм)"] */
// export const disk_diameter: field = ['disk_diameter', "Диаметр диска (мм)"];
// /** ["power", "Мощность"] */
// export const power: field = ['power', "Мощность"];
// /** ["speed_regulation", "Регулировка скорости"] */
// export const speed_regulation: field = ['speed_regulation', "Регулировка скорости"]
// /** ["constant_speed", "Поддержание постоянных оборотов под нагрузкой"] */
// export const constant_speed: field = ['constant_speed', "Поддержание постоянных оборотов под нагрузкой"]
// /** ["revolutions", "Число оборотов"] */
// export const revolutions: field = ['revolutions', "Число оборотов"]
// //#endregion

// //#region Сталь
// /** ['profile_number', "Номер профиля"] */
// export const profile_number: field = ["profile_number", "Номер профиля"]
// /** ["steel_mark", "Марка стали"] */
// export const steel_mark: field = ["steel_mark", "Марка стали"]
// //#endregion

// export const valid_fields: field[] = [name, article, product_id, manufacturer, brand, seller, volume, bookype, isbn]

// /** @deprecated Убран функционал приписки. функция жива, чтоба не сломались парсера
//  - Функция, которая добавляет валидацию к любой переменной. Переменную нужно обернуть в эту функцию.
//  Обратите внимание, что есть переменные, которые имеют автовалидацию, их нельзя оборачивать в эту функцию.
//  Примечание, не забудьте что переменную, которую вы будете валидировать, в коде нужно называть с припиской valid_ */
// export function validateVariable(variable: field): field {
//     return variable
// }

// export function toArray(fields: { [key: string]: field }) {
//     return Array.from(new Set(Object.values(fields)));
// }

// /** Автоматическое создание строки результатов из полей fields */
// export function resultFormatter(fields: field[], separator: string) {
//     let formatter = fields
//         .map((field) => `$${field.at(0)}${separator}`)
//         .join('')
//         .slice(0, -1);
//     return `$items.format('${formatter}\\n')`;
// }