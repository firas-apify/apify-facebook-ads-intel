FROM apify/actor-python-playwright:3.10

# Copy Poetry files
COPY pyproject.toml poetry.lock* ./

# Install Poetry and dependencies
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-ansi

# Install Playwright browsers
RUN playwright install chromium

# Copy source code
COPY . ./

# Run the actor
CMD ["python", "-m", "src.main"]
