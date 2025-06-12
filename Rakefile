# encoding: ascii-8bit

# Copyright 2025 OpenC3, Inc.
# All Rights Reserved.
#
# This program is only licensed for use by the University of Colorado LASP

PLUGIN_NAME = Dir['*.gemspec'][0].split('.')[0..-2].join('.')

task :require_version do
  unless ENV['VERSION']
    puts "VERSION is required: rake <task> VERSION=X.X.X"
    exit 1
  end
end

task :build => [:require_version] do
  _, platform, *_ = RUBY_PLATFORM.split("-")
  if platform == 'mswin32' or platform == 'mingw32'
    puts "Warning: Building gem on Windows will lose file permissions"
  end
  system("gem build #{PLUGIN_NAME}")
end
