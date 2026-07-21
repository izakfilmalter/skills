import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { parse as parseYaml } from "yaml";

const root = process.cwd();
const buckets = ["engineering", "references"];
const errors = [];

const read = (relativePath) =>
  readFile(path.join(root, relativePath), "utf8").catch(() => {
    errors.push(`Missing ${relativePath}`);
    return "";
  });

const skillPaths = [];
for (const bucket of buckets) {
  const directory = path.join(root, "skills", bucket);
  const entries = await readdir(directory, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.isDirectory()) {
      skillPaths.push(`./skills/${bucket}/${entry.name}`);
    }
  }
}
skillPaths.sort();

const packageJson = JSON.parse(await read("package.json"));
const pluginJson = JSON.parse(await read(".claude-plugin/plugin.json"));
const marketplaceJson = JSON.parse(await read(".claude-plugin/marketplace.json"));
const skillsShJson = JSON.parse(await read("skills.sh.json"));
const rootReadme = await read("README.md");

if (packageJson.version !== pluginJson.version) {
  errors.push(
    `Version mismatch: package.json=${packageJson.version}, plugin.json=${pluginJson.version}`,
  );
}

if (marketplaceJson.plugins?.[0]?.name !== pluginJson.name) {
  errors.push("Marketplace plugin name does not match plugin.json");
}

const manifestSkills = [...(pluginJson.skills ?? [])].sort();
if (JSON.stringify(manifestSkills) !== JSON.stringify(skillPaths)) {
  errors.push(
    `Plugin skill list mismatch. Expected ${skillPaths.join(", ")}; received ${manifestSkills.join(", ")}`,
  );
}

const installedSkillNames = new Set(skillPaths.map((skillPath) => path.basename(skillPath)));
const groupedSkillNames = new Set(
  (skillsShJson.groupings ?? []).flatMap((grouping) => grouping.skills ?? []),
);

if (
  JSON.stringify([...groupedSkillNames].sort()) !==
  JSON.stringify([...installedSkillNames].sort())
) {
  errors.push("skills.sh.json groupings do not cover exactly the installed skills");
}

for (const skillPath of skillPaths) {
  const relativeDirectory = skillPath.slice(2);
  const bucket = relativeDirectory.split("/")[1];
  const name = path.basename(relativeDirectory);
  const skillFile = `${relativeDirectory}/SKILL.md`;
  const skill = await read(skillFile);
  const openAiFile = `${relativeDirectory}/agents/openai.yaml`;
  const openAi = await read(openAiFile);
  const docsFile = `docs/${bucket}/${name}.md`;
  const bucketReadme = await read(`skills/${bucket}/README.md`);

  const frontmatterMatch = skill.match(/^---\n([\s\S]*?)\n---\n/);
  if (!frontmatterMatch) {
    errors.push(`${skillFile} has no valid YAML frontmatter block`);
  } else {
    try {
      const frontmatter = parseYaml(frontmatterMatch[1]);
      if (frontmatter.name !== name) errors.push(`${skillFile} name must be ${name}`);
      if (typeof frontmatter.description !== "string" || !frontmatter.description.trim()) {
        errors.push(`${skillFile} needs a description`);
      }
    } catch (error) {
      errors.push(`${skillFile} has invalid YAML: ${error.message}`);
    }
  }
  if (skill.split("\n").length > 100) errors.push(`${skillFile} exceeds 100 lines`);
  try {
    const openAiMetadata = parseYaml(openAi);
    if (
      typeof openAiMetadata?.interface?.display_name !== "string" ||
      typeof openAiMetadata?.interface?.short_description !== "string"
    ) {
      errors.push(`${openAiFile} is missing interface metadata`);
    }
  } catch (error) {
    errors.push(`${openAiFile} has invalid YAML: ${error.message}`);
  }
  await read(docsFile);
  if (!rootReadme.includes(`skills/${bucket}/${name}/SKILL.md`)) {
    errors.push(`README.md does not link ${name}`);
  }
  if (!bucketReadme.includes(`./${name}/SKILL.md`)) {
    errors.push(`skills/${bucket}/README.md does not link ${name}`);
  }

  for (const match of skill.matchAll(/`\/([a-z][a-z0-9-]+)`/g)) {
    const dependency = match[1];
    if (!installedSkillNames.has(dependency)) {
      errors.push(`${skillFile} references missing skill /${dependency}`);
    }
  }
}

if (errors.length > 0) {
  console.error("Skill validation failed:\n");
  for (const error of [...new Set(errors)]) console.error(`- ${error}`);
  process.exit(1);
}

console.log(`Validated ${skillPaths.length} skills and plugin version ${pluginJson.version}.`);
