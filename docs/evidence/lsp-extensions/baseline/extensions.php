<?php

declare(strict_types=1);

use ByteKitsune\MagoSymfonyWiring\SymfonyWiringExtension;
use Mago\Sdk\Analyzer\AfterAnalysisContext;
use Mago\Sdk\Analyzer\AfterAnalysisHook;
use Mago\Sdk\Analyzer\Metadata\MemberIdentifier;
use Mago\Sdk\Analyzer\Plugin;
use Mago\Sdk\Analyzer\PluginDefinition;
use Mago\Sdk\Analyzer\PluginRegistry;
use Mago\Sdk\Extension;
use Mago\Sdk\Worker;

$root = dirname(__DIR__);
require $root . '/vendor/autoload.php';

// A bounded observer of Mago's own graph, not a second parser or analyzer.
$observer = new class implements Plugin, AfterAnalysisHook {
    public function getDefinition(): PluginDefinition
    {
        return new PluginDefinition(
            'poc/wiring-observer',
            'Compiled wiring graph observer',
            'Records selected constructor references from the final native graph.',
        );
    }

    public function register(PluginRegistry $registry): void
    {
        $registry->registerAfterAnalysisHook($this);
    }

    public function afterAnalysis(AfterAnalysisContext $context): void
    {
        $requested = getenv('POC_WIRING_SYMBOLS');
        $owners = $requested === false
            ? ['App\\Form\\Type\\TagsInputType', 'App\\Repository\\TagRepository']
            : json_decode($requested, true, flags: JSON_THROW_ON_ERROR);
        if (!is_array($owners) || count($owners) > 8 || $owners === []) {
            throw new RuntimeException('Expected one to eight selected class names.');
        }
        $symbols = [];
        foreach ($owners as $selected) {
            if (!is_string($selected) || strlen($selected) > 200) {
                throw new RuntimeException('Invalid selected class name.');
            }
            $declaration = $context->codebase->getClassLike($selected);
            $symbols[$selected] = [
                'owner' => $selected,
                'member' => '__construct',
                'declaration' => $declaration === null ? null : [
                    'name' => $declaration->originalName,
                    'location' => $declaration->location,
                    'parent' => $declaration->directParentClass,
                ],
                'references' => array_map(static fn($reference): array => [
                    'source' => $reference->source,
                    'target' => $reference->target,
                    'kind' => $reference->kind->name,
                ], $context->analysis->references->getReferencesFrom(new MemberIdentifier($selected, '__construct'))),
            ];
        }
        // Retain the original slice-1 fields for its independently runnable proof.
        $owner = 'App\\Form\\Type\\TagsInputType';
        $references = [];
        foreach ($context
            ->analysis
            ->references
            ->getReferencesFrom(new MemberIdentifier($owner, '__construct')) as $reference) {
            $references[] = [
                'source' => $reference->source,
                'target' => $reference->target,
                'kind' => $reference->kind->name,
            ];
        }
        $files = [];
        foreach ($context->analysis->files as $file) {
            $files[] = ['path' => $file->file, 'size' => $file->size];
        }
        $file = $context->analysis->getFile('src/Form/Type/TagsInputType.php');
        $record = [
            'observer' => 'poc/wiring-observer',
            'wiring_enabled' => getenv('POC_WIRING') !== '0',
            'owner' => $owner,
            'member' => '__construct',
            'files' => $files,
            'symbols' => $symbols,
            'source_sha256' => $file === null ? null : hash('sha256', $file->getSourceFile()->contents),
            'references' => $references,
            'dependency_declarations' => array_map(static fn($declaration): ?array => (
                $declaration === null
                    ? null
                    : [
                        'name' => $declaration->originalName,
                        'location' => $declaration->location,
                        'parent' => $declaration->directParentClass,
                    ]
            ), $context->codebase->getMultipleClassLikes(['App\\Repository\\TagRepository', 'Doctrine\\Persistence\\ManagerRegistry', 'Doctrine\\Bundle\\DoctrineBundle\\Registry'])),
            'dependency_references' => array_map(static fn($reference): array => [
                'source' => $reference->source,
                'target' => $reference->target,
                'kind' => $reference->kind->name,
            ], $context->analysis->references->getReferencesFrom(new MemberIdentifier('App\\Repository\\TagRepository', '__construct'))),
        ];
        $path = getenv('POC_WIRING_OBSERVATION');
        if (!is_string($path) || !str_starts_with($path, '/evidence/')) {
            throw new RuntimeException('POC_WIRING_OBSERVATION must select a retained /evidence/ file.');
        }
        file_put_contents($path, json_encode($record, JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR) . "\n");
    }
};

$extensions = [new Extension('poc/slice1', 'Slice 1 observation', '1.0.0', analyzerPlugins: [$observer])];
if (getenv('POC_WIRING') !== '0') {
    $extensions[] = SymfonyWiringExtension::fromContainerReference($root, '.mago/container-reference.dev.json');
}
new Worker(...$extensions)->run();
