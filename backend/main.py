from fastapi import FastAPI
from routers import orders, customers, products, tickets, refunds, cancellations, chat

app = FastAPI(title="AI Customer Support API")

app.include_router(orders.router)
app.include_router(customers.router)
app.include_router(products.router)
app.include_router(tickets.router)
app.include_router(refunds.router)
app.include_router(cancellations.router)
app.include_router(chat.router)