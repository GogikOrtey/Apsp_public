
Sorted value_field =
        const name = $("h1.name").text()?.trim() 
        const stock = $(".nal.y").text()?.includes("есть на складе") ? "InStock" : "OutOfStock"
        const price = $(".b").text()?.trim().formatPrice(",")
        const article = $(".char > p:nth-of-type(1)").text()?.trim()
        const brand = $(".char > p:nth-of-type(2)").text()?.trim()
        const imageLink = $("html > body > section.wrap > main > article.wide > .card > .img_bl > .img > a.fancybox")?.first()?.attr("href")?.trim() ? HOST + $("html > body > section.wrap > main > article.wide > .card > .img_bl > .img > a.fancybox")?.first()?.attr("href")?.trim() : ""
        const oldPrice = $(".thr").text()?.trim().formatPrice(",")






    async parseCard(set: SetType, cacher: Cacher<ResultItem[]>) {
        let items: ResultItem[] = []

        const data = await this.makeRequest(set.query);
        const $ = cheerio.load(data);

                const name = $("h1.name").text()?.trim()
const stock = $(".nal.y").text()?.includes("есть 
на складе") ? "InStock" : "OutOfStock"
        const price = $(".b").text()?.trim().formatPrice(",")
        const article = $(".char > p:nth-of-type(1)").text()?.trim()
        const brand = $(".char > p:nth-of-type(2)").text()?.trim()
        const imageLink = $("html > body > section.wrap > main > article.wide > .card > .img_bl > 
.img > a.fancybox")?.first()?.attr("href")?.trim() ? HOST + $("html > body > section.wrap > main > article.wide > .card > .img_bl > .img > a.fancybox")?.first()?.attr("href")?.trim() : ""
        const oldPrice = $(".thr").text()?.trim().formatPrice(",")
        const link = set.query
        const timestamp = getTimestamp()

        const item: ResultItem = {
            name, stock, link, price, article, brand, imageLink, oldPrice, timestamp
        }
        items.push(item);

        cacher.cache = items
        return items;
    }





























