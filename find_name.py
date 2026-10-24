import asyncio
import re
from pathlib import Path

from instagram_username_finder.checker import InstagramChecker, build_session
from instagram_username_finder.models import CheckStatus
from instagram_username_finder.rate_limiter import RateLimiter
from instagram_username_finder.retry import RetryPolicy

WORD_FILE = Path("fresh_words.txt")
CHECKED_FILE = Path("checked_names.txt")
MAX_CHECKS = 1000


def load_words():
    seen = set()
    for line in WORD_FILE.read_text(encoding="utf-8").splitlines():
        word = line.strip().lower()
        if re.fullmatch(r"[a-z]{1,5}", word) and word not in seen:
            seen.add(word)
            yield word


async def main():
    if not WORD_FILE.exists():
        print("Missing fresh_words.txt")
        return

    checked = (
        set(CHECKED_FILE.read_text(encoding="utf-8").splitlines())
        if CHECKED_FILE.exists()
        else set()
    )

    limiter = RateLimiter(concurrency=1, delay=3.0, circuit_threshold=1)
    retries = RetryPolicy(max_retries=1, max_rate_limit_retries=0)
    count = 0

    async with build_session(
        user_agent="InstagramUsernameFinder/0.1 (personal research)",
        concurrency=1,
        timeout=15,
    ) as session:
        checker = InstagramChecker(
            session=session,
            rate_limiter=limiter,
            retry_policy=retries,
            timeout=15,
        )

        for word in load_words():
            if word in checked:
                continue
            if count >= MAX_CHECKS:
                print(f"Stopped at the {MAX_CHECKS}-check limit.")
                break

            result = await checker.check(word)
            count += 1
            print(f"{count}: {word} — {result.status.value}", flush=True)

            if result.status == CheckStatus.RATE_LIMITED:
                print("Instagram limited requests. Stopping.")
                break
            if result.status in {
                CheckStatus.UNKNOWN,
                CheckStatus.TIMEOUT,
                CheckStatus.NETWORK_ERROR,
            }:
                print("Result became unclear. Stopping without claiming availability.")
                break

            with CHECKED_FILE.open("a", encoding="utf-8") as file:
                file.write(word + "\n")

            if result.status == CheckStatus.POSSIBLY_AVAILABLE:
                print(f"\nPOSSIBLE LEAD: {word}")
                print("Check it in Instagram's official username editor.")
                print("Do not assume it is claimable from this result.")
                break
        else:
            print("No unchecked 1–5 letter words remain in fresh_words.txt.")


if __name__ == "__main__":
    asyncio.run(main())