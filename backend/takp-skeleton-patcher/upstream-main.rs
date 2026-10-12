use std::path::PathBuf;

use clap::Parser;

// use libeq::archive::EqArchive;
use libeq::wld::parser;
use libeq_wld::parser::WldDoc;
use serde_json::json;
use zu_common::archive::prelude::*;

#[derive(Debug, Parser)]
#[command(name = "eq_skele_parser")]
struct Cli {
    #[arg(value_name = "s3d file")]
    path: Vec<PathBuf>,
    #[arg(short = 'o', long, value_name = "FILE", required(false))]
    output: Option<PathBuf>,
}

fn main() {
    let args = Cli::parse();

    match args {
        Cli { path, output } => {
            if path.len() > 1 && output.is_some() {
                println!("Output not supported with multiple files");
                return;
            }

            path.iter().for_each(|p| patch_file(p, output.to_owned()));
        }
    }
}

fn patch_file(path: &PathBuf, output: Option<PathBuf>) {
    let out = match output {
        Some(o) => o,
        _ => path.clone(),
    };
    println!("Patching {:?} => {:?}", path, out);

    let wld_filename = match path.file_stem() {
        Some(s) => format!("{}.wld", s.to_ascii_lowercase().to_string_lossy()),
        _ => {
            let mut tmp_path = path.to_owned();
            tmp_path.set_extension("wld");
            tmp_path
                .file_name()
                .expect("Wld filename error")
                .to_ascii_lowercase()
                .to_string_lossy()
                .into()
        }
    };

    // let archive_file = fs::File::open(&path).expect("Failed to open eq archive.");
    // let mut archive = EqArchive::read(archive_file).expect("Failed to parse eq archive.");
    // let (_, wld_data) = archive
    //     .iter()
    //     .find(|(name, _)| name == &wld_filename)
    //     .unwrap();

    let mut archive = ReadWriteArchive::new();
    archive
        .open_file(&path.to_string_lossy())
        .expect("Failed to open eq archive.");

    let wld_data = archive
        .get(&wld_filename)
        .expect("Failed to locate wld in archive.");

    let wld_doc = parser::WldDoc::parse(&wld_data).expect("Failed to parse eq wld");
    let mut wld_json = serde_json::to_value(&wld_doc).expect("Failed to serialize json");
    let strings = wld_json["strings"]
        .as_object_mut()
        .expect("Wld missing strings");

    wld_json["strings"] = strings
        .iter()
        .map(|(k, v)| match v.as_str() {
            Some(s) => {
                let v = &json!(
                    s.replace("SKE", "LSK") // .replace("WOF", "LWF")
                                            // .replace("WOL", "LWL")
                                            // .replace("WOE", "LWE")
                );
                (k, v.clone())
            }
            _ => (k, v.clone()),
        })
        .collect();

    let wld_doc: WldDoc = serde_json::from_value(wld_json).expect("Failed to parse json");

    // archive.remove(&wld_filename);
    // archive.push(&wld_filename, &wld_doc.into_bytes());
    // let bytes = archive.to_bytes().expect("Failed to serialize archive");
    // let mut archive_file = fs::File::create(&out).expect("Failed to create output archive");
    // archive_file
    //     .write_all(&bytes)
    //     .expect("Failed to write output archive");

    archive
        .set(&wld_filename, &wld_doc.into_bytes())
        .expect("Failed to add modified wld to archive");
    archive
        .save_to_file(&out.to_string_lossy())
        .expect("Failed to write output archive");

    println!("Done")
}
