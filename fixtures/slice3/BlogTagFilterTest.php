<?php

declare(strict_types=1);

namespace App\Tests\Controller;

use App\Entity\Post;
use App\Entity\Tag;
use App\Repository\PostRepository;
use PHPUnit\Framework\Attributes\Group;
use Symfony\Bundle\FrameworkBundle\Test\WebTestCase;
use Symfony\Component\DomCrawler\Crawler;

#[Group('slice3')]
final class BlogTagFilterTest extends WebTestCase
{
    public function testKnownTagFilter(): void
    {
        $client = static::createClient();
        $post = static::getContainer()->get(PostRepository::class)->findOneBy([]);
        self::assertInstanceOf(Post::class, $post);
        $tag = $post->getTags()->first();
        self::assertInstanceOf(Tag::class, $tag);

        $crawler = $client->request('GET', '/en/blog/', ['tag' => $tag->getName()]);
        self::assertResponseIsSuccessful();
        $articles = $crawler->filter('article.post');
        self::assertGreaterThan(0, $articles->count());
        $articles->each(static function (Crawler $article) use ($tag): void {
            self::assertSame($tag->getName(), $article->filter('.post-tags .badge-success')->text());
        });
    }
}
