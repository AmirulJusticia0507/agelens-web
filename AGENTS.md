# Instruksi untuk Agent

## Alur Pengerjaan

1. Periksa instruksi repository, status perubahan, dan struktur proyek sebelum mengedit. Pertahankan perubahan yang sudah ada dan jangan menimpa pekerjaan pengguna.
2. Selesaikan task yang diminta dengan perubahan sekecil mungkin. Jika pengguna memberikan beberapa task, kerjakan satu per satu.
3. Setelah task selesai, jalankan test dan pemeriksaan kualitas yang relevan. Jangan menandai task selesai jika validasi yang tersedia gagal.
4. Buat commit untuk perubahan task tersebut, lalu push commit ke remote pada branch kerja yang sedang aktif. Gunakan pesan commit yang jelas dan sertakan trailer:

   ```text
   Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
   ```

5. Setelah task selesai, commit, dan push berhasil, langsung ambil checkbox belum selesai paling atas dari [TODO.md](./TODO.md) dan kerjakan sebagai task berikutnya. Ulangi siklus ini sampai semua task selesai; tidak perlu meminta konfirmasi untuk melanjutkan.
6. Tandai checkbox TODO sebagai selesai hanya setelah implementasi dan validasinya berhasil. Perubahan TODO tersebut harus ikut dalam commit task yang menyelesaikannya.

## Batasan dan Kegagalan

- Kerjakan hanya task yang diminta pengguna dan task berikutnya yang tercatat di `TODO.md`; jangan menambahkan scope baru berdasarkan asumsi.
- Jika ada perubahan pengguna yang belum di-commit, jangan masukkan perubahan tersebut ke commit agent. Stage hanya file yang terkait dengan task yang sedang dikerjakan.
- Jangan pernah melakukan force push, mengubah riwayat bersama, atau memasukkan rahasia dan data sensitif ke commit.
- Push hanya branch kerja aktif. Jangan berpindah branch atau mengubah pengaturan remote untuk mengakali kegagalan push.
- Jika test penting gagal, ada perubahan yang berkonflik, akses remote tidak tersedia, atau push ditolak, berhenti sebelum melanjutkan ke task berikutnya. Laporkan blocker dan hasil yang sudah dicapai dengan jelas; jangan mengklaim commit atau push berhasil jika belum.
- Jangan meminta konfirmasi untuk langkah rutin yang telah diizinkan oleh alur ini. Berhenti dan minta arahan hanya bila blocker tidak dapat diselesaikan dengan aman atau membutuhkan keputusan produk yang belum tercakup dalam dokumentasi.
