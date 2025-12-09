# Работа с isBadLink.
1. Надо сделать импорт field из `"../Base-Custom/Fields"`
2. Применить данное поле, как flat. Если у вас getDefaultConf, то надо 3 аргументов передать массив полей, которые будут flat полями.
```typescript
...getDefaultConf(toArray(fields), "§", [isBadLink])
```
Пример `Base-baucenter` `Base-citilinkru`

Если у вас legacy описание полей парсера, то надо в conf.results добавить flat со значением массива flat полей
``` typescript      
results: {
    arrays: {
        items: ['Items list', [...fields]]
    },
    flat: [isBadLink]
},
```
Пример `Puppeteer-rs24ru`

3. В обработке `NotFoundError` сделать `results.isBadLink = 1;` для обозначение кривой ссылки.

Пример `Base-baucenter` `Base-citilinkru`

4. \* Если в парсере идет валидация ссылки, то надо вызвать исключение `InvalidLinkError` из `"../Base-Custom/Errors"`. Также эту ошибку надо обработать как `NotFoundError`
```typescript
if (error instanceof NotFoundError || error instanceof InvalidLinkError)
```
Пример `Flare-ozonru` `Base-onlinetraderu`