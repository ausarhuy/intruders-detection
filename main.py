import argparse
import asyncio
import os
import tracemalloc

from dotenv import load_dotenv

from detector import PersonDetection
from notifications import Notification


async def run_detector(capture_index):
    # Load environment variables
    load_dotenv()

    password = os.environ.get("INTRUSALERTS_PASSWORD")
    from_email = os.environ.get("INTRUSALERTS_FROM_EMAIL")
    to_email = os.environ.get("INTRUSALERTS_TO_EMAIL")

    # Instanciate Notification and PersonDetection classes
    email_notification = Notification(from_email, to_email, password)
    detector = PersonDetection(capture_index=capture_index, email_notification=email_notification)

    # Detect
    await detector.start()


def main(capture_index):
    # Enable tracemalloc for debugging memory leaks
    tracemalloc.start()

    # Run the detector asynchronously
    asyncio.run(run_detector(capture_index))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the person detection system.")
    parser.add_argument('--capture_index', default=1,
                        help='The index or IP Address of the camera to be used for capture.')
    args = parser.parse_args()

    main(args.capture_index)
