
import json
import httpx

from langchain_core.tools import tool


@tool
def search_products(search_term: str = "", limit: int = 5) -> str:
    """
    Search the online store's product catalog.

    Use this tool when customers ask about:
    - Available products
    - Product prices
    - Product descriptions
    - Product stock availability
    - Products matching a name or category

    search_term: A short product name or keyword.
    For example, use "SSD" instead of "portable SSDs".
    Use an empty string to list products generally.

    limit: Maximum number of products to retrieve.
    """

    print(
        f"PRODUCT TOOL STARTED: {search_term}",
        flush=True
    )

    # 1. Limit the number of products
    limit = max(1, min(limit, 10))

    # 2. Call our existing products API
    try:
        response = httpx.get(
            "http://127.0.0.1:8000/products",
            params={
                "search": search_term,
                "limit": limit
            },
            timeout=10.0
        )

        response.raise_for_status()

    except httpx.HTTPError:
        return "Unable to retrieve products right now."

    # 3. Read the products returned by FastAPI
    products = response.json()

    if not products:
        return "No matching products were found."

    print(
        f"PRODUCT TOOL CALLED: {len(products)} products found",
        flush=True
    )

    # 4. Return the product details to the LLM
    return json.dumps({
        "products": products
    })
