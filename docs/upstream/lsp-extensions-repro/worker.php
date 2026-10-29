<?php
// Explicit regression plugin: this contributes a test edge, not Symfony facts.
declare(strict_types=1);
require $argv[1];
use Mago\Sdk\Analyzer\{AfterAnalysisContext, AfterAnalysisHook, AfterFileAnalysisContext, AfterFileAnalysisHook};
use Mago\Sdk\Analyzer\{Plugin, PluginDefinition, PluginRegistry};
use Mago\Sdk\Analyzer\Metadata\MemberIdentifier;
use Mago\Sdk\{Extension, Worker};
file_put_contents(getenv('MAGO_REPRO_STARTS'), "worker-started\n", FILE_APPEND);
$plugin = new class implements Plugin, AfterFileAnalysisHook, AfterAnalysisHook {
    public function getDefinition(): PluginDefinition {
        return new PluginDefinition('poc/lsp-regression', 'LSP worker regression', 'Adds one explicit test dependency.');
    }
    public function register(PluginRegistry $registry): void {
        $registry->registerAfterFileAnalysisHook($this);
        $registry->registerAfterAnalysisHook($this);
    }
    public function getRequirements(): array { return []; }
    public function afterFileAnalysis(AfterFileAnalysisContext $context): void {
        if (basename($context->analysis->file) === 'Example.php') {
            $context->references->add(new MemberIdentifier('Repro\\Service', '__construct'), 'Repro\\Concrete');
        }
    }
    public function afterAnalysis(AfterAnalysisContext $context): void {
        $references = $context->analysis->references->getReferencesFrom(new MemberIdentifier('Repro\\Service', '__construct'));
        $graph = array_map(static fn($edge): array => ['kind' => $edge->kind->name, 'target' => $edge->target], $references);
        file_put_contents(getenv('MAGO_REPRO_GRAPH'), json_encode($graph, JSON_THROW_ON_ERROR) . "\n");
    }
};
new Worker(new Extension('poc/lsp-regression', 'LSP regression fixture', '1.0.0', analyzerPlugins: [$plugin]))->run();
