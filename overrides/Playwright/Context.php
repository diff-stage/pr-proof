<?php

declare(strict_types=1);

namespace Pest\Browser\Playwright;

use Exception;
use PrProof\Recorder;
use PrProof\Telemetry;

/**
 * @internal
 */
final class Context
{
    use Concerns\InteractsWithPlaywright;

    /**
     * Indicates whether the browser context is closed.
     */
    private bool $closed = false;

    private ?Tracing $tracing = null;

    private ?string $videoPath = null;

    /**
     * @var array<int, string>
     */
    private array $videoArtifacts = [];

    /**
     * Creates a new context instance.
     */
    public function __construct(
        private readonly Browser $browser,
        private readonly string $guid,
        private readonly ?string $tracingGuid = null,
    ) {
        //
    }

    public function tracing(): ?Tracing
    {
        if ($this->tracingGuid === null) {
            return null;
        }

        return $this->tracing ??= new Tracing($this->tracingGuid);
    }

    /**
     * Gets the browser instance.
     */
    public function browser(): Browser
    {
        return $this->browser;
    }

    /**
     * Creates a new page in the context.
     */
    public function newPage(): Page
    {
        $response = Client::instance()->execute($this->guid, 'newPage');

        $frameGuid = '';
        $pageGuid = '';

        /** @var array{method: string|null, params: array{type: string|null, guid: string, initializer: array{url: string}}, result: array{page: array{guid: string|null}}} $message */
        foreach ($response as $message) {
            if (($message['method'] ?? null) === '__create__' && ($message['params']['type'] ?? null) === 'Artifact') {
                $this->videoArtifacts[] = $message['params']['guid'];
            }

            if (isset($message['method']) && $message['method'] === '__create__' && (isset($message['params']['type']) && $message['params']['type'] === 'Frame')) {
                $frameGuid = $message['params']['guid'];
            }

            if (isset($message['result']['page']['guid'])) {
                $pageGuid = $message['result']['page']['guid'];
            }
        }

        return new Page($this, $pageGuid, $frameGuid);
    }

    /**
     * Closes the browser context.
     */
    public function close(): void
    {
        if ($this->browser->isClosed() || $this->closed) {
            return;
        }

        try {
            // fix this...
            $response = $this->sendMessage('close');
            $this->processVoidResponse($response);
        } catch (Exception $e) {
            if (str_contains($e->getMessage(), 'has been closed')) {
                return;
            }

            throw $e;
        }

        $this->saveVideos();

        $this->closed = true;
    }

    /**
     * Saves the videos of this context to the given path once it closes.
     */
    public function recordTo(string $path): self
    {
        $this->videoPath = $path;

        return $this;
    }

    /**
     * Asks the browser to report console messages and network results for this context.
     */
    public function subscribeToProblems(): self
    {
        foreach (['console', 'request', 'response', 'requestFailed'] as $event) {
            iterator_to_array($this->sendMessage('updateSubscription', ['event' => $event, 'enabled' => true]));
        }

        return $this;
    }

    private function saveVideos(): void
    {
        if ($this->videoPath === null) {
            return;
        }

        file_put_contents(
            (string) preg_replace('/\.webm$/', '.json', $this->videoPath),
            (string) json_encode(Telemetry::finish(), JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE),
        );

        foreach ($this->videoArtifacts as $index => $artifact) {
            $path = $index === 0 ? $this->videoPath : preg_replace('/\.webm$/', '-'.($index + 1).'.webm', $this->videoPath);

            iterator_to_array(Client::instance()->execute($artifact, 'saveAs', ['path' => $path]));

            Recorder::saved($this->videoPath);
        }
    }

    /**
     * Checks if the browser context is closed.
     */
    public function isClosed(): bool
    {
        return $this->closed;
    }

    /**
     * Adds a script which will be evaluated.
     */
    public function addInitScript(string $script): self
    {
        $response = $this->sendMessage('addInitScript', ['source' => $script]);
        $this->processVoidResponse($response);

        return $this;
    }
}
