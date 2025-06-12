# encoding: ascii-8bit

# Copyright 2025 OpenC3, Inc.
# All Rights Reserved.
#
# This program is only licensed for use by the University of Colorado LASP

# Create the overall gemspec
spec = Gem::Specification.new do |s|
  s.name = 'openc3-cosmos-script-engine-cstol'
  s.summary = 'OpenC3 Script Engine CSTOL'
  s.description = <<-EOF
  This plugin provides a script engine to support CSTOL in Script Runner
  EOF
  s.authors = ['Ryan Melton']
  s.email = ['ryan@openc3.com']
  s.homepage = 'https://github.com/OpenC3/openc3-cosmos-script-engine-cstol'

  s.platform = Gem::Platform::RUBY

  if ENV['VERSION']
    s.version = ENV['VERSION'].dup
  else
    time = Time.now.strftime("%Y%m%d%H%M%S")
    s.version = '0.0.0' + ".#{time}"
  end
  s.licenses = ['Nonstandard']

  s.files = Dir.glob("{targets,lib,procedures,tools,microservices}/**/*") + %w(Rakefile LICENSE.txt README.md plugin.txt)
end
