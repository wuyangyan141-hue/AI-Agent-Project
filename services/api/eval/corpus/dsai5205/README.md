# DSAI5205 eval corpus (local copies)

Course chapter PDFs for RAG evaluation are **not** committed (size / redistribution).
From the repository root, copy them from your machine:

```powershell
.\scripts\sync-eval-corpus.ps1
# or: .\scripts\sync-eval-corpus.ps1 -SourceDir "D:\path\to\5205"
```

Expected files:

- `DSAI5205_Chapter3_2026.pdf`
- `DSAI5205_Chapter4_2026.pdf`
- `DSAI5205_Chapter5_2026.pdf`
- `DSAI5205_Chapter6.pdf`

The gold set also uses `eval/corpus/search_basics.txt` for detailed search-algorithm drill questions.