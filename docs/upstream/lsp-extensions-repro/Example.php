<?php
namespace Repro;
interface Port {}
final class Concrete implements Port {}
final class Service {
    public function __construct(public Port $port) {}
}
