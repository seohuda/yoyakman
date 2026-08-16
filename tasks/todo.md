# 코드 리뷰(xhigh) 지적사항 전량 수정

리뷰 대상: `bot.py` (슬래시 커맨드 전환 커밋 이후 상태)
검증 기준: discord.py 2.7.x 소스 직접 확인 + 함수 실제 실행

## 커밋 1 — 무응답 버그 (치명)

- [ ] `on_app_command_error`가 `defer()` 이후에도 응답하도록 수정
      (`response.is_done()`이면 `followup.send`)
- [ ] `/요약`에서 `interaction.channel is None`인 경우 안내 후 종료
- [ ] 컨텍스트 메뉴는 `interaction.channel` 대신 `message.channel` 사용
      (`namespace.py:225-233` — 항상 `PartialMessageable`로 채워짐)

## 커밋 2 — 보안

- [ ] `AllowedMentions.none()` 설정 (닉네임에 심은 `@everyone`/롤 멘션이 실제로 울림)
- [ ] 닉네임에도 `escape_mentions` 적용
- [ ] 대화 로그를 경계 구분자로 감싸고, 그 안은 데이터로만 취급하도록 프롬프트에 명시
- [ ] 메시지 본문에서 경계 구분자 문자열 제거

## 커밋 3 — 예외 처리 범위

- [ ] `except (Forbidden, HTTPException)` → 권한 계열(`Forbidden`, `NotFound`)만 잡기
- [ ] 그 외 HTTP 오류는 로그와 함께 tree 에러 핸들러로 전파
- [ ] `setup_hook`의 `tree.sync()`를 try/except로 감싸 기동 실패 방지

## 커밋 4 — 쿨다운

- [ ] 쿨다운 데코레이터를 한 번만 생성해 두 명령이 버킷을 공유 (현재 분당 6회)
- [ ] 남은 시간 표시를 `math.ceil`로 (0초 안내 방지)

## 커밋 5 — 경계 조건

- [ ] `split_for_discord`가 빈 청크를 만들지 않도록 (`followup.send("")` → 400)
- [ ] 컨텍스트 메뉴 폴백에도 `author.bot` 필터 적용
- [ ] 시작 메시지 포함 시 총 개수가 100을 넘지 않도록
- [ ] 수집 결과가 비었을 때도 `notice`를 함께 안내

## 커밋 6 — 정리

- [ ] `collect_recent` / `collect_from_message` 공통 루프 통합
- [ ] `commands.Bot(command_prefix=...)` → `discord.Client` + `CommandTree`

## Review

(구현 후 작성)
