<?php

namespace PocFixture;

interface Greeter
{
    public function greet(string $name): string;
}

class FriendlyGreeter implements Greeter
{
    public function greet(string $name): string
    {
        return 'Hello '.$name;
    }
}

class LoudGreeter extends FriendlyGreeter
{
    public function greet(string $name): string
    {
        return strtoupper(parent::greet($name));
    }
}

function welcome(Greeter $greeter): string
{
    return $greeter->greet('World');
}
