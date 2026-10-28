<?php

declare(strict_types=1);

namespace App\Tests\Command;

use App\Entity\Tag;
use Doctrine\ORM\EntityManagerInterface;
use PHPUnit\Framework\Attributes\Group;
use Symfony\Bundle\FrameworkBundle\Console\Application;
use Symfony\Bundle\FrameworkBundle\Test\KernelTestCase;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Tester\CommandTester;

#[Group('slice2')]
final class TagsCountCommandTest extends KernelTestCase
{
    public function testEmptyDatabase(): void
    {
        $this->assertCountForTags([], 0);
    }

    public function testPopulatedDatabase(): void
    {
        $this->assertCountForTags(['slice-two-a', 'slice-two-b', 'slice-two-c'], 3);
    }

    /**
     * @param list<string> $names
     */
    private function assertCountForTags(array $names, int $expected): void
    {
        $kernel = self::bootKernel();
        /** @var EntityManagerInterface $manager */
        $manager = self::getContainer()->get(EntityManagerInterface::class);
        $connection = $manager->getConnection();
        $connection->executeStatement('DELETE FROM symfony_demo_post_tag');
        $connection->executeStatement('DELETE FROM symfony_demo_tag');
        $manager->clear();

        foreach ($names as $name) {
            $manager->persist(new Tag($name));
        }
        $manager->flush();

        $application = new Application($kernel);
        $tester = new CommandTester($application->find('app:tags:count'));
        $exit = $tester->execute([]);

        self::assertSame(Command::SUCCESS, $exit);
        self::assertSame(\sprintf("Tag count: %d\n", $expected), $tester->getDisplay());
    }
}
