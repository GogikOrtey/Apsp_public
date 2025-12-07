async parseCard(set: SetType, cacher: Cacher<ResultItem[]>) {
    let items: ResultItem[] = []

    const data = await this.makeRequest(set.query);
    const $ = cheerio.load(data);

    const stock = $(".nal.y").text()?.includes("есть на складе") ? "InStock" : "OutOfStock"   
    const name = $("h1.name").text()?.trim() 
    const price = $(".b").text()?.trim().formatPrice(",")
    const article = $(".char > p:nth-of-type(1)").text()?.trim()
    const brand = $(".char > p:nth-of-type(2)").text()?.trim()
    const imageLink = $("html > body > section.wrap > main > article.wide > .card > .img_bl > .img > a.fancybox")?.first()?.attr("href")?.trim() ? HOST + $("html > body > section.wrap > main > article.wide > .card > .img_bl > .img > a.fancybox")?.first()?.attr("href")?.trim() : ""
    const oldPrice = $(".thr").text()?.trim().formatPrice(",")
    const link = set.query
    const timestamp = getTimestamp()

    const item: ResultItem = {
        name, price, article, brand, imageLink, oldPrice, stock, timestamp, link
    }
    items.push(item);

    cacher.cache = items
    return items;
}

































