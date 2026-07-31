"""#128 원오프 — 이미 적재된 activities에 venue 정제·공고성 삭제를 소급 적용한다.

로더(load_source_data)는 다음 크롤부터 같은 규칙을 적용하므로, 이 스크립트는 현재 DB를
같은 상태로 맞추는 1회성 도구다. 삭제 항목의 accessibility_scores·mission_copy도 함께
정리한다(참조 무결성 — 남아 있어도 무해하지만 지저분하다).
"""
import psycopg2

from .load_source_data import database_url
from .venue_quality import clean_venue_name, is_non_activity


def refresh() -> None:
    with psycopg2.connect(database_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("select activity_id, name, venue_name from activities")
            rows = cursor.fetchall()
            removed, renamed = [], 0
            for activity_id, name, venue in rows:
                if is_non_activity(name):
                    removed.append(activity_id)
                    continue
                cleaned = clean_venue_name(venue)
                if cleaned != venue:
                    cursor.execute(
                        "update activities set venue_name=%s where activity_id=%s",
                        (cleaned, activity_id),
                    )
                    renamed += 1
            if removed:
                cursor.execute("delete from accessibility_scores where activity_id = any(%s)", (removed,))
                scores = cursor.rowcount
                cursor.execute("delete from mission_copy where activity_id = any(%s)", (removed,))
                copies = cursor.rowcount
                cursor.execute("delete from activities where activity_id = any(%s)", (removed,))
                print(f"공고성 삭제 {len(removed)}건 (+scores {scores}·copy {copies} 정리)")
            print(f"venue 정제 {renamed}건 / 전체 {len(rows)}건")


if __name__ == "__main__":
    refresh()
