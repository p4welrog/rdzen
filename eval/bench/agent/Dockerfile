# SPDX-License-Identifier: MIT OR Apache-2.0
# Obraz agenta dla wariantów AP i AR: Python + Z3 + Claude Code, bez repozytorium Rdzenia.
# Kompilator (bez eval/) i skill są montowane tylko w wariancie AR (agent.py).
FROM node:22-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir --break-system-packages z3-solver \
    && npm install -g @anthropic-ai/claude-code

RUN useradd --create-home --shell /bin/bash agent && mkdir /praca && chown agent /praca
USER agent
# katalog ustawień tworzy użytkownik agent; skill jest montowany jako jego podkatalog
RUN mkdir -p /home/agent/.claude/skills
WORKDIR /praca
ENV CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 DISABLE_AUTOUPDATER=1
