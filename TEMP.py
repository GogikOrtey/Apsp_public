from new_program.html_toolkit import run_js_parsePage_get_card_links


def main():
    user_code = """
async parsePage(set) {
  for (let i = 1; i <= 15; i++) {
    this.query.add({ type: "card", query: "https://example.com/p/" + set.query + "/" + i });
  }
}
""".strip()

    res = run_js_parsePage_get_card_links(user_code=user_code, query="test-query")
    print(res)


if __name__ == "__main__":
    main()


