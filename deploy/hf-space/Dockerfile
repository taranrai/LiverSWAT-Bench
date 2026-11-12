# Hugging Face Docker Space: resume the LiverSWAT-Bench Milestone 5 judge stage on a GPU.
# The image runs the same Ollama version as the laptop pilot (0.40.6), pinned by digest.
# GitHub is the source repository. The build clones one exact commit (LSB_GIT_REF).
FROM ollama/ollama:0.40.6@sha256:265409e1d931028a8f7d5a32bcbafddd7bffbc6cc629d77efe9560adf692a5e7

# Space variables are passed to the build as build arguments.
ARG LSB_GIT_URL=https://github.com/taranrai/LiverSWAT-Bench.git
ARG LSB_GIT_REF=""

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv git ca-certificates curl

# Hugging Face runs the container as user ID 1000.
ENV HOME=/home/lsb \
    LSB_REPO_DIR=/home/lsb/repo \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_MODELS=/home/lsb/.ollama/models
RUN mkdir -p /home/lsb && chown 1000:1000 /home/lsb
USER 1000
WORKDIR /home/lsb

RUN echo "$LSB_GIT_REF" | grep -Eq '^[0-9a-f]{40}$' \
    || { echo "Set the Space variable LSB_GIT_REF to a full 40-character commit SHA"; exit 1; }
RUN git init -q repo \
    && git -C repo remote add origin "$LSB_GIT_URL" \
    && git -C repo fetch -q --depth 1 origin "$LSB_GIT_REF" \
    && git -C repo checkout -q --detach FETCH_HEAD \
    && test "$(git -C repo rev-parse HEAD)" = "$LSB_GIT_REF"

RUN python3 -m venv /home/lsb/venv \
    && /home/lsb/venv/bin/pip install --no-cache-dir -e "/home/lsb/repo[space]"
ENV PATH=/home/lsb/venv/bin:$PATH

COPY --chown=1000:1000 entrypoint.sh status_server.py /home/lsb/space/

EXPOSE 7860
ENTRYPOINT ["bash", "/home/lsb/space/entrypoint.sh"]
