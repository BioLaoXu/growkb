#' 计算 peak 注释表中 promoter 区域占比
#'
#' 按客户常用口径统计注释结果里落在启动子区域的 peak 比例。
#' 适用于 ChIPseeker annotatePeak 输出表（含 annotation 列）。
#'
#' @param peaks 数据框，必须包含 `annotation` 列（ChIPseeker 区域类型，如 "Promoter (<=1kb)"）
#' @param promoter_level 字符串向量，判定为 promoter 的前缀，默认 c("Promoter", "proximal")
#' @return 数据框，含 `region`（区域类型）与 `ratio`（占比 0-1），按占比降序
#' @export
#' @examples
#' d <- data.frame(annotation = c("Promoter (<=1kb)", "Intron (intron_1)",
#'                               "Promoter (<=1kb)", "Intergenic"))
#' promoter_ratio(d)
promoter_ratio <- function(peaks, promoter_level = c("Promoter", "proximal")) {
  stopifnot(is.data.frame(peaks), "annotation" %in% names(peaks))
  is_promo <- vapply(peaks$annotation, function(a) {
    any(vapply(promoter_level, function(p) startsWith(a, p), logical(1)))
  }, logical(1))
  tab <- as.data.frame(prop.table(table(Region = ifelse(is_promo, "Promoter", "Other"))))
  names(tab)[2] <- "ratio"
  tab[order(-tab$ratio), ]
}
