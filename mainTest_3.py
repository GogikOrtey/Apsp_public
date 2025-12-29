# # # Подключение всех библиотек
# # from import_all_libraries import * 

# # now = int(time.time())
# # print(now)

# # Собирает название парсера из хоста
# def set_parser_name(host):
#     # Как нужно чистим домен
#     parser_file_name = host.split("://")[1].split("/")[0]
#     parser_file_name = parser_file_name.replace("www.", "")
#     parser_file_name = parser_file_name.replace(".", "").replace("-", "")
#     # TODO регионы потом удалять, но это сильно позже

#     base_name_part = "JS_Base_" + parser_file_name
#     print("Имя парсера: " + base_name_part)

#     return base_name_part

# host = "https://makitaclub.ru"
# set_parser_name(host)

async parsePage(set: SetType) {
    const url = new URL("https://sort.diginetica.net/search")
    const pageSize = 500;
    const urlParam = {
        st: set.query,
  
      apiKey: "NY2D9562L7",
        strategy: "advanced_xname,zero_queries",
        fullData: true,
        withCorrection: true,
        withFacets: true,
        treeFacets: true,
        regionId: "global",
       
 useCategoryPrediction: false,
        size: pageSize,
        offset: set.offset,
    
    showUnavailable: true,
        unavailableMultiplier: 0.2,
        preview: false,
        withSku: false,
        sort: "DEFAULT",
    };

    const data = await this.makeRequest(url.href, set.region, urlParam)
 
   const json = JSON.parse(data);

    if (json.totalHits == 0) {
        this.logger.put(`По запросу ${set.query} ничего не найдено`)
        throw new NotFoundError()
    }

    if (set.offset === 0) {
        const totalPages = Math.ceil(json.totalHits / pageSize);
        for (let shift = 1; shift <= 
Math.min(totalPages, +this.conf.pagesCount); 
shift++) {
            this.query.add(({ ...set, query: set.query, type: "page", offset: 
shift * pageSize, lvl: 1 }));
        }
   
 }

    json.products.slice(0, +this.conf.itemsCount).forEach(product => {
        let 
link = `https://elemis.ru${product?.link_url}`
        this.query.add({ ...set, query: link, type: "card", lvl: 1 })
    })
}