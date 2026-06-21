const { withAppBuildGradle } = require('@expo/config-plugins');

/**
 * Remove the deprecated enableBundleCompression property from build.gradle
 */
module.exports = function withAndroidBuildGradle(config) {
  return withAppBuildGradle(config, (config) => {
    if (config.modResults.contents) {
      // Remove enableBundleCompression line
      config.modResults.contents = config.modResults.contents.replace(
        /enableBundleCompression\s*=\s*false/g,
        ''
      );
      config.modResults.contents = config.modResults.contents.replace(
        /enableBundleCompression\s*=\s*true/g,
        ''
      );
    }
    return config;
  });
};
