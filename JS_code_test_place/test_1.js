// const fs = require('fs');
// const path = require('path');
// const cheerio = require('cheerio');

// // Read the saved HTML page
// const htmlPath = path.join(__dirname, 'page_html.html');
// const html = fs.readFileSync(htmlPath, 'utf8');

// // Parse with cheerio
// const $ = cheerio.load(html);

// // // Grab all pagination numbers (current page + links), ignore dots/arrows
// // // const selector = 'nav.woocommerce-pagination .page-numbers a, nav.woocommerce-pagination .page-numbers span';
// // const selector = 'nav.woocommerce-pagination';
// // let totalPages = Math.max(...$(selector).get().map(item => +$(item).text().trim()).filter(Boolean))

// // console.log('totalPages:', totalPages);


// let HOST = "https://makitaclub.ru"
// let products = $('.products .card a.stretched-link')
// let product = products?.eq(0)
// let link = HOST + $(product)?.attr('href')
// console.log("link = " + link)



// let url = new URL(`${HOST}/catalog/`)        
// url.searchParams.set('type', 'catalog')      
// url.searchParams.set('s', 'Найти')
// url.searchParams.set('q', set.query)
// if (+set.page > 1) url.searchParams.set('PAGEN_2', String(set.page))
// else url.searchParams.delete('PAGEN_2')   


// let url = set.page && +set.page > 1 ? new URL(`${HOST}/page/${set.page}/`) : new URL(`${HOST}/`)
// url.searchParams.set('s', set.query)
// url.searchParams.set('post_type', 'product')

// let totalPages = Math.max(...$("nav.woocommerce-pagination .page-numbers").get().map(item => +$(item).text().trim()).filter(Boolean))


let products = $('.products .product-card a.stretched-link[href*="/products/"]')
let product = products?.eq(0)
let link = $(product)?.attr('href')
console.log('link = ' + link)


    //#region Парсинг товара
    async parseCard(set: SetType, cacher: Cacher<ResultItem[]>) {
        let items: ResultItem[] = []

        const data = await this.makeRequest(set.query);
        const $ = cheerio.load(data);        

        const name = $("h1.product_title.entry-title").first().text().trim()
        const price = $("p.price .woocommerce-Price-amount").first().text().trim()?.replace(/\s+/g, " ")?.replace(/,/g, ".")?.replace(/[^\d.]/g, "")
        const imageLink = $(".woocommerce-product-gallery img.wp-post-image").first()?.attr("data-large_image") || $(".woocommerce-product-gallery img.wp-post-image").first()?.attr("data-src") || $(".woocommerce-product-gallery img.wp-post-image").first()?.attr("src") || ""
        const article = $(".product_meta .sku_wrapper .sku").first().text().trim()        
        const addToCartText = $("form.cart .single_add_to_cart_button, form.cart button.single_add_to_cart_button, button.single_add_to_cart_button")?.first().text().trim(); const 
stock = addToCartText?.includes("В корзину") 
? "InStock" : "OutOfStock";
        const timestamp = getTimestamp()     

        const item: ResultItem = {
            name, price, imageLink, article, 
stock, link, timestamp
        }
        items.push(item);

        cacher.cache = items
        return items;
    }