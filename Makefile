.DEFAULT_GOAL := help

.PHONY: help check

help:
	@printf '%s\n' 'help  Pokaż dostępne polecenia' 'check Sprawdź komentarze i wpisy o autorstwie'

check:
	@tools/check-comments
	@tools/check-attribution
