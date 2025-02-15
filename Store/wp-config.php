<?php

/**
 * The base configuration for WordPress
 *
 * The wp-config.php creation script uses this file during the installation.
 * You don't have to use the website, you can copy this file to "wp-config.php"
 * and fill in the values.
 *
 * This file contains the following configurations:
 *
 * * Database settings
 * * Secret keys
 * * Database table prefix
 * * ABSPATH
 *
 * @link https://developer.wordpress.org/advanced-administration/wordpress/wp-config/
 *
 * @package WordPress
 */

// ** Database settings - You can get this info from your web host ** //
/** The name of the database for WordPress */
define( 'DB_NAME', 'khaqanmi_wp572' );

/** Database username */
define( 'DB_USER', 'khaqanmi_wp572' );

/** Database password */
define( 'DB_PASSWORD', '4Nq-0p85S!' );

/** Database hostname */
define( 'DB_HOST', 'localhost' );

/** Database charset to use in creating database tables. */
define( 'DB_CHARSET', 'utf8mb4' );

/** The database collate type. Don't change this if in doubt. */
define( 'DB_COLLATE', '' );

/**#@+
 * Authentication unique keys and salts.
 *
 * Change these to different unique phrases! You can generate these using
 * the {@link https://api.wordpress.org/secret-key/1.1/salt/ WordPress.org secret-key service}.
 *
 * You can change these at any point in time to invalidate all existing cookies.
 * This will force all users to have to log in again.
 *
 * @since 2.6.0
 */
define( 'AUTH_KEY',         'igx7izpqyvkqz9d6hqdw4hsfr7z6e8ib77dodal75rm1ze0uqxcxffoyfijatd7j' );
define( 'SECURE_AUTH_KEY',  'uwhd6am748d5yyqmymunhotlabeavq4l2w3vw2gymqmaph9olywwwhbn7sfelnuu' );
define( 'LOGGED_IN_KEY',    '1urmp8squwyggabsdegces8lgtjabgoatgrs9qp6nbhwil2nu8djhrt74bing1is' );
define( 'NONCE_KEY',        'q9n1npczaqz7mrlmmehmlcfdd17kjgea0qfyyxj0okqgwavknoj4fjvmbhg7gekv' );
define( 'AUTH_SALT',        'tgkz53ckjanwab5dqkd8bn8iqum8xovxcpfv3hvs7iywubxleko3z3syue5ckfu9' );
define( 'SECURE_AUTH_SALT', 'u6djljighwg6rpos9ej6dufqnq67sldgaor5gaorzsyvuxy1aem7w0qi0620zfq2' );
define( 'LOGGED_IN_SALT',   'dl2ctrgejxqhgfothezf87ib1dnzb9lhw62jcenvhqywto4cpkyoov824kk30s4l' );
define( 'NONCE_SALT',       'f65vmybdnep5dkay8xyh92uiyqoftwk5svrqgp91qews9gsafpr41c5wtw6eqteg' );

/**#@-*/

/**
 * WordPress database table prefix.
 *
 * You can have multiple installations in one database if you give each
 * a unique prefix. Only numbers, letters, and underscores please!
 *
 * At the installation time, database tables are created with the specified prefix.
 * Changing this value after WordPress is installed will make your site think
 * it has not been installed.
 *
 * @link https://developer.wordpress.org/advanced-administration/wordpress/wp-config/#table-prefix
 */
$table_prefix = 'wpuz_';

/**
 * For developers: WordPress debugging mode.
 *
 * Change this to true to enable the display of notices during development.
 * It is strongly recommended that plugin and theme developers use WP_DEBUG
 * in their development environments.
 *
 * For information on other constants that can be used for debugging,
 * visit the documentation.
 *
 * @link https://developer.wordpress.org/advanced-administration/debug/debug-wordpress/
 */
define( 'WP_DEBUG', false );

/* Add any custom values between this line and the "stop editing" line. */

/* That's all, stop editing! Happy publishing. */

/** Absolute path to the WordPress directory. */
if ( ! defined( 'ABSPATH' ) ) {
	define( 'ABSPATH', __DIR__ . '/' );
}

/** Sets up WordPress vars and included files. */
require_once ABSPATH . 'wp-settings.php';
