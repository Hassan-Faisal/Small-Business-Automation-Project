import asyncio

from app.services.openai_service import openai_service


async def main():
    response = await openai_service.generate_response(
        "Introduce yourself in one short paragraph."
    )

    print(response)


if __name__ == "__main__":
    asyncio.run(main())