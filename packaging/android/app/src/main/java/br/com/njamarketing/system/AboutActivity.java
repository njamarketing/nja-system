package br.com.njamarketing.system;

import android.app.DownloadManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.Settings;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.FileProvider;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class AboutActivity extends AppCompatActivity {
    private static final String RELEASE_API = "https://api.github.com/repos/njamarketing/nja-system/releases/latest";
    private static final String APK_NAME = "NJA-System-Android.apk";

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private TextView updateStatus;
    private Button updateButton;
    private String latestVersion;
    private String latestDownloadUrl;
    private long activeDownload = -1;
    private File pendingInstaller;
    private boolean receiverRegistered;

    private final BroadcastReceiver downloadReceiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            if (DownloadManager.ACTION_DOWNLOAD_COMPLETE.equals(intent.getAction())
                    && intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1) == activeDownload) {
                handleCompletedDownload();
            }
        }
    };

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        setContentView(R.layout.activity_about);
        configureSafeAreas();

        findViewById(R.id.about_back).setOnClickListener(view -> finish());
        ((TextView) findViewById(R.id.about_version)).setText(getString(R.string.version_label, BuildConfig.VERSION_NAME));
        updateStatus = findViewById(R.id.update_status);
        updateButton = findViewById(R.id.update_button);
        updateButton.setOnClickListener(view -> {
            if (latestDownloadUrl == null) checkForUpdates(); else downloadUpdate();
        });
        registerDownloadReceiver();
        checkForUpdates();
    }

    private void configureSafeAreas() {
        WindowInsetsControllerCompat controller = WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        controller.setAppearanceLightStatusBars(false);
        controller.setAppearanceLightNavigationBars(false);
        View root = findViewById(R.id.about_root);
        ViewCompat.setOnApplyWindowInsetsListener(root, (view, windowInsets) -> {
            Insets bars = windowInsets.getInsets(WindowInsetsCompat.Type.systemBars()
                    | WindowInsetsCompat.Type.displayCutout());
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return windowInsets;
        });
        ViewCompat.requestApplyInsets(root);
    }

    private void registerDownloadReceiver() {
        IntentFilter filter = new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(downloadReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(downloadReceiver, filter);
        }
        receiverRegistered = true;
    }

    private void checkForUpdates() {
        latestVersion = null;
        latestDownloadUrl = null;
        updateStatus.setText(R.string.update_checking);
        updateButton.setEnabled(false);
        executor.execute(() -> {
            try {
                HttpURLConnection connection = (HttpURLConnection) new URL(RELEASE_API).openConnection();
                connection.setConnectTimeout(10_000);
                connection.setReadTimeout(10_000);
                connection.setRequestProperty("Accept", "application/vnd.github+json");
                connection.setRequestProperty("User-Agent", "NJA-System-Android/" + BuildConfig.VERSION_NAME);
                if (connection.getResponseCode() != HttpURLConnection.HTTP_OK) throw new IllegalStateException("HTTP " + connection.getResponseCode());
                StringBuilder body = new StringBuilder();
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(connection.getInputStream(), StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = reader.readLine()) != null) body.append(line);
                } finally {
                    connection.disconnect();
                }
                JSONObject release = new JSONObject(body.toString());
                String version = release.getString("tag_name").replaceFirst("^[vV]", "");
                String download = findApk(release.getJSONArray("assets"));
                runOnUiThread(() -> showUpdateResult(version, download));
            } catch (Exception error) {
                runOnUiThread(() -> {
                    updateStatus.setText(R.string.update_failed);
                    updateButton.setText(R.string.update_again);
                    updateButton.setEnabled(true);
                });
            }
        });
    }

    private String findApk(JSONArray assets) throws Exception {
        for (int i = 0; i < assets.length(); i++) {
            JSONObject asset = assets.getJSONObject(i);
            if (APK_NAME.equals(asset.optString("name"))) return asset.getString("browser_download_url");
        }
        throw new IllegalStateException("APK não encontrado");
    }

    private void showUpdateResult(String version, String download) {
        if (compareVersions(version, BuildConfig.VERSION_NAME) > 0) {
            latestVersion = version;
            latestDownloadUrl = download;
            updateStatus.setText(getString(R.string.update_available, "v" + version));
            updateButton.setText(getString(R.string.update_now, "v" + version));
        } else {
            updateStatus.setText(R.string.update_current);
            updateButton.setText(R.string.update_again);
        }
        updateButton.setEnabled(true);
    }

    static int compareVersions(String left, String right) {
        String[] a = left.split("\\.");
        String[] b = right.split("\\.");
        for (int i = 0; i < Math.max(a.length, b.length); i++) {
            int av = i < a.length ? numericPart(a[i]) : 0;
            int bv = i < b.length ? numericPart(b[i]) : 0;
            if (av != bv) return Integer.compare(av, bv);
        }
        return 0;
    }

    private static int numericPart(String value) {
        String digits = value.replaceAll("[^0-9].*$", "");
        return digits.isEmpty() ? 0 : Integer.parseInt(digits);
    }

    private void downloadUpdate() {
        if (latestDownloadUrl == null || latestVersion == null) return;
        File directory = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
        if (directory == null) {
            Toast.makeText(this, R.string.update_download_failed, Toast.LENGTH_LONG).show();
            return;
        }
        pendingInstaller = new File(directory, "NJA-System-" + latestVersion + ".apk");
        if (pendingInstaller.exists() && !pendingInstaller.delete()) {
            Toast.makeText(this, R.string.update_download_failed, Toast.LENGTH_LONG).show();
            return;
        }
        DownloadManager.Request request = new DownloadManager.Request(Uri.parse(latestDownloadUrl));
        request.setTitle("NJA System v" + latestVersion);
        request.setDescription(getString(R.string.update_downloading));
        request.setMimeType("application/vnd.android.package-archive");
        request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
        request.setDestinationInExternalFilesDir(this, Environment.DIRECTORY_DOWNLOADS, pendingInstaller.getName());
        activeDownload = ((DownloadManager) getSystemService(DOWNLOAD_SERVICE)).enqueue(request);
        updateStatus.setText(R.string.update_downloading);
        updateButton.setEnabled(false);
    }

    private void handleCompletedDownload() {
        DownloadManager manager = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        try (Cursor cursor = manager.query(new DownloadManager.Query().setFilterById(activeDownload))) {
            if (cursor != null && cursor.moveToFirst()
                    && cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS)) == DownloadManager.STATUS_SUCCESSFUL) {
                updateStatus.setText(R.string.update_downloaded);
                installDownloadedApk();
                return;
            }
        }
        updateStatus.setText(R.string.update_download_failed);
        updateButton.setEnabled(true);
    }

    private void installDownloadedApk() {
        if (pendingInstaller == null || !pendingInstaller.isFile()) return;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !getPackageManager().canRequestPackageInstalls()) {
            Intent permission = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + getPackageName()));
            startActivity(permission);
            return;
        }
        Uri apk = FileProvider.getUriForFile(this, getPackageName() + ".files", pendingInstaller);
        Intent install = new Intent(Intent.ACTION_VIEW)
                .setDataAndType(apk, "application/vnd.android.package-archive")
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(install);
        pendingInstaller = null;
    }

    @Override protected void onResume() {
        super.onResume();
        if (pendingInstaller != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                && getPackageManager().canRequestPackageInstalls()) installDownloadedApk();
    }

    @Override protected void onDestroy() {
        if (receiverRegistered) unregisterReceiver(downloadReceiver);
        executor.shutdownNow();
        super.onDestroy();
    }
}
