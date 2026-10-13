# Data distribution review / 数据分发审查

Reviewed 2026-10-13. Code and synthetic examples are Apache-2.0. This licence does
not grant rights over third-party datasets. The two real-data packages are retained
locally, not published in this repository. Public and journal/reviewer distribution
are evaluated separately.

| Source | Evidence | Public / reviewer redistribution finding |
|---|---|---|
| EPO TIP / PATSTAT | Project handoffs identify TIP PATSTAT PROD. [TIP](https://www.epo.org/en/searching-for-patents/data/technology-intelligence-platform) links to the [website terms](https://www.epo.org/en/terms-of-use/terms-and-conditions-use-website-european-patent-office). | Not confirmed for the complete derivative event database; both routes pending. |
| PATSTAT-specific terms | [Terms](https://www.epo.org/en/service-support/ordering/patstat-data-terms-and-conditions), own-product and redistribution provisions. | Some free derivative products may be allowed; applicability to historical TIP extraction and third-party content is not established. |
| USPTO AIPD | [Official dataset](https://www.uspto.gov/ip-policy/economic-research/research-datasets/artificial-intelligence-patent-dataset). | Public official source; preserve attribution. Does not resolve other components' permissions. |
| PatentsView classifications | [Official platform documentation](https://search.patentsview.org/docs/2024/08/23/2.1.2-release) identifies CC BY 4.0 for API data. | Attribution required; confirm applicable bulk snapshot terms before treating API wording as a licence for every file. |
| AIPat scores | [Upstream](https://github.com/yusu2022/AIPat-Data-and-Methods-for-Identifying-Artificial-Intelligence-Related-Patents), source commit `24621519e2d7bf63bb6c609b0e632ab657629124`. | README invites use and citation; no explicit redistribution licence found in inspected root/README. Both routes unconfirmed. |

EPO website sections 6.4 and 6.6 retain conditions for adaptations, substantial
database copies and third-party information. Download availability is not blanket
permission for a full downloadable database. This review does not assert a legal
prohibition where permission is simply unresolved.

当前结论是“尚未确认”，不是“已明确禁止”。需确认的是衍生专利族/引用事件数据库和AIPat
分数能否作为免费公开数据包或期刊附件再分发，不需要把账户取得过程加入自动化。
代码可单独发布，真实数据可交回原数据持有人本地核验，暂不声明已获第三方分发许可。

No provider has been contacted automatically. Hashing identifiers, changing file
formats or using the code licence does not settle these permissions. The manifests
preserve the unresolved status.
